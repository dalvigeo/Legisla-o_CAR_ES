from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "textos"


def load_normas():
    js = (
        "global.window={};require('./data.js');require('./data-current.js');"
        "process.stdout.write(JSON.stringify(window.NORMAS));"
    )
    proc = subprocess.run(["node", "-e", js], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def load_js(path: Path, prefix: str, fallback):
    if not path.exists():
        return fallback
    raw = path.read_text(encoding="utf-8").strip()
    if not raw.startswith(prefix):
        return fallback
    body = raw[len(prefix):].strip()
    if body.endswith(';'):
        body = body[:-1]
    return json.loads(body)


def save_js(path: Path, prefix: str, value):
    path.write_text(prefix + json.dumps(value, ensure_ascii=False, indent=2) + ';\n', encoding='utf-8')


def normalize(value: str) -> str:
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()


def suspicious_ratio(text: str) -> float:
    if not text:
        return 1.0
    allowed_extra = set('áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇºª§–—“”‘’…')
    weird = 0
    meaningful = 0
    for ch in text:
        if ch.isspace():
            continue
        meaningful += 1
        if ch.isascii() or ch in allowed_extra:
            continue
        if ch.isalpha() and 'LATIN' in unicodedata.name(ch, ''):
            continue
        weird += 1
    return weird / max(1, meaningful)


def garbage_tokens(text: str) -> float:
    tokens = re.findall(r'\S+', text)
    if not tokens:
        return 1.0
    bad = 0
    for token in tokens:
        chars = [c for c in token if not c.isspace()]
        if len(chars) < 5:
            continue
        symbols = sum(1 for c in chars if not (c.isalpha() or c.isdigit() or c in '.,;:()/-ºª§%'))
        if symbols / len(chars) > .28:
            bad += 1
    return bad / max(1, len(tokens))


def is_trusted_structured_html(source: dict) -> bool:
    url = str(source.get('textSourceUrl', '')).lower()
    label = str(source.get('textSourceLabel', '')).lower()
    trusted_domains = [
        'camara.leg.br',
        'legisweb.com.br',
        'normasbrasil.com.br',
        'revistaprocampo.com.br',
        'taxesbrasil.com.br',
        'ribmg.org.br',
        'lex.com.br',
        'irib.org.br',
        'gov.br/',
        'in.gov.br',
    ]
    trusted_labels = ['texto atualizado', 'texto consolidado', 'legislação informatizada', 'reprodução integral']
    return any(domain in url for domain in trusted_domains) or any(term in label for term in trusted_labels)


def markup_reason(soup: BeautifulSoup) -> str | None:
    article_ids = [tag.get('id') for tag in soup.select('[id^="art-"]') if tag.get('id')]
    duplicates = [key for key, count in Counter(article_ids).items() if count > 1]
    if duplicates:
        return 'artigos duplicados indicam mistura de colunas ou de atos distintos (' + ', '.join(duplicates[:4]) + ')'

    text = normalize(soup.get_text(' ', strip=True))
    contamination = [
        'resumo do contrato',
        'ordem de servico',
        'ordem de fornecimento',
        'valor total',
        'conceder recesso aos estagiario',
        'grupo de recursos humanos',
        'extrato do edital de notificacao',
        'departamento de edificacoes e de rodovias',
        'concessao de uso seag',
    ]
    hits = [marker for marker in contamination if marker in text]
    strong = {
        'ordem de servico', 'ordem de fornecimento', 'conceder recesso aos estagiario',
        'extrato do edital de notificacao'
    }
    if len(hits) >= 2 or any(hit in strong for hit in hits):
        return 'conteúdo de outro ato administrativo misturado à norma durante a leitura do Diário Oficial'
    return None


def quality_reason(text: str, norma: dict, strict_structure: bool = True, strict_tokens: bool = True) -> str | None:
    plain = re.sub(r'\s+', ' ', text).strip()
    n = normalize(plain)
    if len(plain) < 160:
        return 'texto excessivamente curto'
    if suspicious_ratio(plain) > .012:
        return 'alta proporção de glifos inválidos na camada textual do documento'
    if strict_tokens and garbage_tokens(plain) > .035:
        return 'padrão de tokens corrompidos na extração textual'

    if strict_structure:
        tipo = norma.get('tipo', '').lower()
        if any(x in tipo for x in ['lei', 'decreto', 'instrução normativa', 'resolução']):
            legal_markers = sum(marker in n for marker in ['art 1', 'resolve', 'decreta', 'fac o saber', 'presidente', 'governador', 'diretor'])
            if legal_markers == 0 and len(plain) > 600:
                return 'estrutura normativa não reconhecida no texto extraído'
    return None


def unavailable_html(norma: dict, url: str, reason: str) -> str:
    return f'''<section class="texto-norma texto-indisponivel" data-norma-id="{norma['id']}">
<div class="notice"><strong>Transcrição automática bloqueada por controle de qualidade.</strong> {reason}. O documento-fonte permanece disponível para consulta direta enquanto uma transcrição confiável é preparada.</div>
<p><a href="{url}" target="_blank" rel="noopener">Acessar fonte utilizada ↗</a></p>
</section>'''


def main():
    normas = load_normas()
    sources = load_js(ROOT / 'generated-sources.js', 'window.NORM_SOURCES = ', {})
    report_path = ROOT / 'generated-report.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'errors': []}
    errors = list(report.get('errors', []))
    bad_ids = set()

    deliberate_pending = {'in-idaf-008-2014-barragens', 'in-idaf-009-2014-barragens'}

    for norma in normas:
        nid = norma['id']
        if nid in deliberate_pending:
            bad_ids.add(nid)
            continue
        path = TEXT_DIR / f'{nid}.html'
        if not path.exists():
            bad_ids.add(nid)
            continue
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        if soup.select_one('.texto-indisponivel'):
            bad_ids.add(nid)
            continue

        source = sources.get(nid, {})
        trusted_html = is_trusted_structured_html(source)

        reason = None if trusted_html else markup_reason(soup)
        if not reason:
            reason = quality_reason(
                soup.get_text(' ', strip=True),
                norma,
                strict_structure=not trusted_html,
                strict_tokens=not trusted_html,
            )
        if not reason:
            continue

        if source.get('manualValidated'):
            continue

        bad_ids.add(nid)
        url = source.get('textSourceUrl') or source.get('officialUrl') or norma.get('fonteUrl', '#')
        path.write_text(unavailable_html(norma, url, reason), encoding='utf-8')
        source['available'] = False
        source['qualityBlocked'] = True
        source['note'] = (source.get('note', '') + ' Extração bloqueada: ' + reason + '.').strip()
        sources[nid] = source
        errors.append({'id': nid, 'error': 'controle de qualidade: ' + reason, 'source': url})

    index = []
    for norma in normas:
        nid = norma['id']
        if nid in bad_ids:
            continue
        path = TEXT_DIR / f'{nid}.html'
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True)).strip()
        if text:
            index.append({'id': nid, 'text': text[:450000]})

    dedup = []
    seen = set()
    for item in errors:
        key = (item.get('id'), item.get('error'))
        if key not in seen:
            seen.add(key)
            dedup.append(item)

    approved = [n['id'] for n in normas if n['id'] not in bad_ids and sources.get(n['id'], {}).get('available')]
    report.update({
        'success': sorted(set(approved)),
        'errors': dedup,
        'quality_blocked': sorted(bad_ids),
        'total_normas': len(normas),
        'total_com_texto': len(set(approved)),
        'total_pendentes': len(bad_ids),
    })
    save_js(ROOT / 'generated-index.js', 'window.NORM_TEXT_INDEX = ', index)
    save_js(ROOT / 'generated-sources.js', 'window.NORM_SOURCES = ', sources)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Auditoria: {len(approved)}/{len(normas)} aprovadas; {len(bad_ids)} bloqueadas/pendentes.")


if __name__ == '__main__':
    main()
