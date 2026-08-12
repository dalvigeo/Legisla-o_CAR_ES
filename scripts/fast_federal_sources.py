from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_legislation as base
import enrich_generated as enrich

TEXT_DIR = ROOT / 'textos'


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
    raw = path.read_text(encoding='utf-8').strip()
    if not raw.startswith(prefix):
        return fallback
    body = raw[len(prefix):].strip()
    if body.endswith(';'):
        body = body[:-1]
    return json.loads(body)


def save_js(path: Path, prefix: str, value):
    path.write_text(prefix + json.dumps(value, ensure_ascii=False, indent=2) + ';\n', encoding='utf-8')


def process_camara(norma, cfg):
    # Alguns metadados vieram com barra final; urljoin trataria o .html como diretório.
    meta_url = cfg['text_source_url'].rstrip('/')
    actual_url, label = enrich.resolve_camara(meta_url, norma['id'])
    text, final_url, kind = enrich.extract_standard(actual_url)
    return norma, cfg, text, final_url, label, kind


def process_direct_url(norma, cfg, url, label=None):
    text, final_url, kind = enrich.extract_standard(url)
    return norma, cfg, text, final_url, label or cfg.get('text_source_label', norma.get('fonte', 'Fonte')), kind


def process_direct(norma, cfg):
    return process_direct_url(norma, cfg, cfg['text_source_url'])


def write_text(norma, cfg, text, final_url, label, kind, sources):
    formatted = base.format_html(text, norma, final_url, label)
    (TEXT_DIR / f"{norma['id']}.html").write_text(formatted, encoding='utf-8')
    previous = sources.get(norma['id'], {})
    sources[norma['id']] = {
        **previous,
        'officialUrl': norma.get('fonteUrl', '') or previous.get('officialUrl', ''),
        'textSourceUrl': final_url,
        'textSourceLabel': label,
        'sourceKind': kind,
        'available': True,
        'qualityBlocked': False,
        'note': cfg.get('note', previous.get('note', ''))
    }


def main():
    normas = load_normas()
    by_id = {n['id']: n for n in normas}
    cfgs = json.loads((ROOT / 'source_overrides.json').read_text(encoding='utf-8'))
    sources_path = ROOT / 'generated-sources.js'
    sources = load_js(sources_path, 'window.NORM_SOURCES = ', {})
    report_path = ROOT / 'generated-report.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'errors': []}
    errors = list(report.get('errors', []))
    success = set(report.get('success', []))

    jobs = []
    for nid, cfg in cfgs.items():
        norma = by_id.get(nid)
        url = cfg.get('text_source_url', '')
        if not norma or norma.get('esfera') != 'Federal' or not url:
            continue
        if nid.startswith('in-icmbio-'):
            continue
        fn = process_camara if 'www2.camara.leg.br/legin/' in url else process_direct
        jobs.append((fn, norma, cfg))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fn, norma, cfg): norma['id'] for fn, norma, cfg in jobs}
        for future in as_completed(futures):
            nid = futures[future]
            try:
                norma, cfg, text, final_url, label, kind = future.result()
                write_text(norma, cfg, text, final_url, label, kind, sources)
                success.add(nid)
            except Exception as exc:
                cfg = cfgs.get(nid, {})
                errors.append({'id': nid, 'error': 'fonte federal: ' + str(exc), 'source': cfg.get('text_source_url', '')})

    # ICMBio: prioriza fontes oficiais atuais; usa reproduções apenas como fallback.
    historic_in5 = 'https://www.gov.br/icmbio/pt-br/assuntos/consolidacao-territorial/IN__5_DE_19_DE_MAIO_DE_2016.pdf'
    icmbio_raw = {}
    for nid in ['in-icmbio-5-2016', 'in-icmbio-24-2025', 'in-icmbio-16-2026']:
        norma = by_id.get(nid)
        cfg = cfgs.get(nid, {})
        if not norma:
            continue

        candidates = []
        if nid == 'in-icmbio-5-2016':
            candidates.append((historic_in5, 'ICMBio — arquivo oficial histórico'))
        elif norma.get('fonteUrl'):
            candidates.append((norma['fonteUrl'], 'Diário Oficial da União — fonte oficial'))
        if cfg.get('text_source_url'):
            candidates.append((cfg['text_source_url'], cfg.get('text_source_label', norma.get('fonte', 'Fonte'))))

        last_error = None
        for url, label in candidates:
            try:
                result = process_direct_url(norma, cfg, url, label)
                norma2, cfg2, text, final_url, label2, kind = result
                icmbio_raw[nid] = (text, final_url, label2, kind)
                write_text(norma2, cfg2, text, final_url, label2, kind, sources)
                success.add(nid)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            errors.append({'id': nid, 'error': 'ICMBio: ' + str(last_error), 'source': candidates[-1][0] if candidates else ''})

    if 'in-icmbio-24-2025' in icmbio_raw and 'in-icmbio-16-2026' in icmbio_raw:
        base_text, base_url, _, base_kind = icmbio_raw['in-icmbio-24-2025']
        amendment_text = icmbio_raw['in-icmbio-16-2026'][0]
        norma = by_id['in-icmbio-24-2025']
        consolidated = enrich.consolidate_in24(base_text, amendment_text)
        label = 'IN ICMBio nº 24/2025 — texto consolidado editorialmente com a IN nº 16/2026'
        cfg = dict(cfgs.get('in-icmbio-24-2025', {}))
        cfg['note'] = 'Consolidação editorial com as alterações da IN ICMBio nº 16/2026; as publicações oficiais permanecem identificadas.'
        write_text(norma, cfg, consolidated, base_url, label, base_kind, sources)

    report['success'] = sorted(success)
    report['errors'] = errors
    save_js(sources_path, 'window.NORM_SOURCES = ', sources)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Atualização federal incremental: {len(jobs)} fontes da Câmara/União processadas em paralelo.')


if __name__ == '__main__':
    main()
