from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import fitz
import requests
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_legislation as base  # noqa: E402

TEXT_DIR = ROOT / "textos"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "LegislaCAR/1.0 (+https://github.com/dalvigeo/LegislaCAR)"})


def load_normas() -> list[dict]:
    js = (
        "global.window={};require('./data.js');require('./data-current.js');"
        "process.stdout.write(JSON.stringify(window.NORMAS));"
    )
    proc = subprocess.run(["node", "-e", js], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def load_js_json(path: Path, prefix: str, fallback):
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith(prefix):
        return fallback
    raw = text[len(prefix):].strip()
    if raw.endswith(";"):
        raw = raw[:-1]
    return json.loads(raw)


def save_js_json(path: Path, prefix: str, value) -> None:
    path.write_text(prefix + json.dumps(value, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


def resolve_camara(meta_url: str, norma_id: str) -> tuple[str, str]:
    response = SESSION.get(meta_url, timeout=45, allow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    updated = []
    originals = []
    republications = []
    for a in soup.find_all("a", href=True):
        label = base.normalize(a.get_text(" ", strip=True))
        href = urljoin(response.url, a["href"])
        if "texto atualizado" in label and "html" in label:
            updated.append(href)
        elif "texto publicacao original" in label:
            originals.append(href)
        elif label.startswith("republicacao") and "atualizada" not in label:
            republications.append(href)

    if norma_id == "decreto-23793-1934" and republications:
        # A última republicação da Câmara contém o Código Florestal completo.
        return republications[-1], "Câmara dos Deputados — republicação do ato histórico"
    if updated:
        return updated[0], "Câmara dos Deputados — Texto Atualizado (HTML)"
    if originals:
        return originals[0], "Câmara dos Deputados — Publicação Original"
    raise RuntimeError("a Câmara não apresentou link para texto atualizado ou publicação original")


def extract_standard(url: str) -> tuple[str, str, str]:
    text, final_url, kind = base.extract_text(url)
    text = base.remove_site_chrome(text)
    if len(text) < 180:
        raise RuntimeError("texto extraído muito curto")
    return text, final_url, kind


def write_norm(norma: dict, text: str, source_url: str, source_label: str, sources: dict, note: str = "", official_url: str | None = None) -> None:
    formatted = base.format_html(text, norma, source_url, source_label)
    (TEXT_DIR / f"{norma['id']}.html").write_text(formatted, encoding="utf-8")
    sources[norma["id"]] = {
        "officialUrl": official_url or norma.get("fonteUrl", source_url),
        "textSourceUrl": source_url,
        "textSourceLabel": source_label,
        "available": True,
        "note": note,
    }


def write_unavailable(norma: dict, sources: dict, message: str) -> None:
    url = norma.get("fonteUrl", "#")
    html = f'''<section class="texto-norma texto-indisponivel" data-norma-id="{norma['id']}">
<div class="notice"><strong>Texto integral ainda não localizado em fonte documental confiável.</strong> {message}</div>
<p><a href="{url}" target="_blank" rel="noopener">Acessar referência oficial disponível ↗</a></p>
</section>'''
    (TEXT_DIR / f"{norma['id']}.html").write_text(html, encoding="utf-8")
    sources[norma["id"]] = {
        "officialUrl": url,
        "textSourceUrl": url,
        "textSourceLabel": norma.get("fonte", "Referência cadastrada"),
        "available": False,
        "note": message,
    }


def extract_idaf_001_2023(pdf_url: str) -> tuple[str, str]:
    """Extrai o ato de um PDF de Diário Oficial em múltiplas colunas.

    Testa a página inteira e recortes esquerdo/direito; escolhe a leitura que
    contém mais marcadores do ato do Idaf e rejeita texto vizinho de contratos.
    """
    response = SESSION.get(pdf_url, timeout=60, allow_redirects=True)
    response.raise_for_status()
    doc = fitz.open(stream=response.content, filetype="pdf")
    candidates: list[tuple[float, str]] = []
    markers = ["instrução normativa", "idaf", "art. 1", "art. 32", "020/2017", "020", "barragens"]
    penalties = ["valor total", "ordem de fornecimento", "contrato", "pregão"]

    for page in doc:
        w, h = page.rect.width, page.rect.height
        clips = [
            page.rect,
            fitz.Rect(0, 0, w * 0.52, h),
            fitz.Rect(w * 0.48, 0, w, h),
            fitz.Rect(0, 0, w * 0.58, h),
            fitz.Rect(w * 0.42, 0, w, h),
        ]
        for clip in clips:
            text = base.clean_extracted_text(page.get_text("text", clip=clip, sort=True))
            n = base.normalize(text)
            score = sum(n.count(base.normalize(m)) * 8 for m in markers)
            score += min(len(text), 2500) / 250
            score -= sum(n.count(base.normalize(p)) * 12 for p in penalties)
            if "art 1" in n and "art 32" in n:
                score += 40
            candidates.append((score, text))

    if not candidates:
        raise RuntimeError("PDF sem texto extraível")
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]

    # Recorta o conteúdo ao ato normativo propriamente dito.
    start = re.search(r"(?is)(INSTRU[ÇC][ÃA]O\s+NORMATIVA[^\n]*001[^\n]*2023|O\s+diretor-presidente\s+do\s+Instituto\s+de\s+Defesa)", best)
    if start:
        best = best[start.start():]
    end = re.search(r"(?is)(LEONARDO\s+CUNHA\s+MONTEIRO.*?Diretor[-– ]Presidente|Código de Autenticação:[^\n]+)", best)
    if end:
        best = best[:end.end()]

    n = base.normalize(best)
    if "art 1" not in n or "art 32" not in n:
        raise RuntimeError("não foi possível isolar o art. 1º e a nova redação do art. 32 no PDF oficial")
    return best.strip(), response.url


def current_art32_from_amendment(text: str) -> str | None:
    # A nova redação aparece entre aspas após 'Art. 32'. Captura até o encerramento
    # da citação ou até o art. 2º da norma alteradora.
    m = re.search(r"(?is)(Art\.\s*32\.?[^\n]*.*?)(?=\n\s*Art\.\s*2[º°o]?|\n\s*Vitória|\n\s*Esta\s+Instrução|$)", text)
    if not m:
        return None
    block = m.group(1).strip().strip('"“”')
    return block if len(block) > 80 else None


def replace_html_article(path: Path, article_id: str, new_paragraphs: list[tuple[str, str]]) -> bool:
    if not path.exists():
        return False
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    article = soup.find(id=article_id)
    if not article:
        return False
    parent = article.parent
    node = article.next_sibling
    while node is not None:
        nxt = node.next_sibling
        if isinstance(node, Tag) and node.name == "p" and "norm-artigo" in (node.get("class") or []):
            break
        if isinstance(node, Tag):
            node.decompose()
        node = nxt
    article.string = new_paragraphs[0][1]
    article["class"] = [new_paragraphs[0][0]]
    cursor = article
    for cls, text in new_paragraphs[1:]:
        tag = soup.new_tag("p")
        tag["class"] = [cls]
        tag.string = text
        cursor.insert_after(tag)
        cursor = tag
    path.write_text(str(soup), encoding="utf-8")
    return True


def patch_decreto_3346(sources: dict) -> None:
    path = TEXT_DIR / "decreto-es-3346-r-2013.html"
    current = [
        ("norm-artigo", "Art. 12. O IDAF só emitirá licenças ambientais e autorizações de queima controlada mediante apresentação do documento ‘Solicitação de Inscrição no Cadastro Ambiental Rural - CAR’."),
        ("norm-paragrafo", "Parágrafo único. A emissão de autorização de exploração florestal dependerá de análise e aprovação das informações declaradas na Solicitação de Inscrição no Cadastro Ambiental Rural - CAR."),
    ]
    if replace_html_article(path, "art-12", current):
        item = sources.get("decreto-es-3346-r-2013", {})
        note = item.get("note", "")
        item["note"] = (note + " Art. 12 consolidado com a redação dada pelo Decreto Estadual nº 4.139-R/2017.").strip()
        sources["decreto-es-3346-r-2013"] = item


def patch_in20_art32(amendment_text: str, sources: dict) -> bool:
    current = current_art32_from_amendment(amendment_text)
    if not current:
        return False
    path = TEXT_DIR / "in-idaf-020-2017.html"
    if not replace_html_article(path, "art-32", [("norm-artigo", current)]):
        return False
    item = sources.get("in-idaf-020-2017", {})
    item["note"] = "Art. 32 consolidado com a redação dada pela Instrução Normativa Idaf nº 001/2023."
    sources["in-idaf-020-2017"] = item
    return True


def replace_section(text: str, start_pattern: str, end_pattern: str, replacement: str) -> str:
    pattern = re.compile(start_pattern + r".*?(?=" + end_pattern + r")", re.I | re.S | re.M)
    if pattern.search(text):
        return pattern.sub(replacement.strip() + "\n\n", text, count=1)
    return text


def extract_annex(text: str, number: str, next_marker: str) -> str | None:
    p = re.compile(rf"(?ims)^\s*ANEXO\s+{number}\b.*?(?=^\s*{next_marker}\b)")
    m = p.search(text)
    return m.group(0).strip() if m else None


def consolidate_in24(base_text: str, amendment_text: str) -> str:
    # Inciso V do art. 2º.
    current_v = "V – Doador Beneficiário: é o doador definido no inciso IV, que por meio da doação do imóvel ao ICMBio, situado em Unidade de Conservação federal pendente de regularização fundiária, beneficia-se diretamente da doação com a compensação de passivo ambiental em imóvel ou empreendimento próprio;"
    base_text = re.sub(
        r"(?ims)^\s*V\s*[–—-]\s*Doador Beneficiário:.*?(?=^\s*VI\s*[–—-])",
        current_v + "\n",
        base_text,
        count=1,
    )

    # Exclui a alínea 'd' revogada no inciso III do art. 33 quando identificável.
    base_text = re.sub(
        r"(?ims)^\s*d\)\s*[^\n]*(?:órgão ambiental competente|orgao ambiental competente)[^\n]*\n?",
        "",
        base_text,
        count=1,
    )

    # § 2º do art. 33.
    current_33_2 = "§ 2º A responsabilidade relativa à comunicação e à quitação do compromisso de compensação de reserva legal ou de outras modalidades de compensação junto ao órgão ambiental competente é do interessado."
    base_text = re.sub(
        r"(?ims)^\s*§\s*2[º°o]?\s+.*?(?=^\s*§\s*3|^\s*Art\.\s*34\b)",
        current_33_2 + "\n",
        base_text,
        count=1,
    )

    art34 = """Art. 34. O ICMBio poderá receber, em doação antecipada, imóveis situados em Unidades de Conservação federais, mediante acordo de cooperação com os órgãos ambientais competentes.
§ 1º Na ausência de acordo de cooperação técnica, o doador será cientificado de que a utilização da área doada como medida compensatória dependerá de anuência expressa do órgão ambiental competente, a qual deverá ser apresentada ao ICMBio previamente à averbação na matrícula do imóvel.
§ 2º Para fins do disposto neste artigo, considera-se órgão ambiental competente aquele responsável pela aprovação da compensação de reserva legal ou de outras medidas compensatórias, situado no estado onde se localiza o imóvel com passivo ambiental a ser compensado."""
    art35 = """Art. 35. O ICMBio regulamentará os procedimentos operacionais da doação antecipada por meio de ato normativo específico, sem prejuízo da operacionalização imediata do mecanismo mediante os acordos de cooperação com os órgãos ambientais competentes ou mediante anuência expressa conforme previsto no art. 34.
Art. 35-A. Para cada destinação de área doada antecipadamente como medida compensatória, o ICMBio providenciará averbação específica na matrícula do imóvel, observadas as condições previstas no art. 34, contendo a identificação do beneficiário, a área utilizada, a finalidade da compensação, o órgão ambiental competente e o saldo remanescente disponível."""
    base_text = replace_section(base_text, r"^\s*Art\.\s*34\b", r"^\s*Art\.\s*35\b", art34)
    base_text = replace_section(base_text, r"^\s*Art\.\s*35\b", r"^\s*Art\.\s*36\b", art35)

    # Os anexos I, II e III foram integralmente substituídos pela IN 16/2026.
    annex1 = extract_annex(amendment_text, "I", "ANEXO\s+II")
    annex2 = extract_annex(amendment_text, "II", "ANEXO\s+III")
    annex3 = extract_annex(amendment_text, "III", "Art\.\s*3")
    for num, annex, next_marker in [
        ("I", annex1, r"ANEXO\s+II"),
        ("II", annex2, r"ANEXO\s+III"),
        ("III", annex3, r"ANEXO\s+IV"),
    ]:
        if annex:
            base_text = replace_section(base_text, rf"^\s*ANEXO\s+{num}\b", rf"^\s*{next_marker}\b", annex)
    return base_text


def rebuild_index(normas: list[dict]) -> list[dict]:
    index = []
    for norma in normas:
        path = TEXT_DIR / f"{norma['id']}.html"
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if soup.select_one(".texto-indisponivel"):
            continue
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
        if text:
            index.append({"id": norma["id"], "text": text[:450000]})
    return index


def main() -> None:
    normas = load_normas()
    by_id = {n["id"]: n for n in normas}
    overrides = json.loads((ROOT / "source_overrides.json").read_text(encoding="utf-8"))
    sources = load_js_json(ROOT / "generated-sources.js", "window.NORM_SOURCES = ", {})
    old_report = json.loads((ROOT / "generated-report.json").read_text(encoding="utf-8")) if (ROOT / "generated-report.json").exists() else {"errors": []}
    errors = []
    success = set()

    # Substitui as falhas do Planalto por fonte legislativa da Câmara.
    for nid, override in overrides.items():
        norma = by_id.get(nid)
        if not norma:
            continue
        source = override.get("text_source_url", "")
        if "www2.camara.leg.br/legin/" not in source:
            continue
        try:
            actual, label = resolve_camara(source, nid)
            text, final_url, _ = extract_standard(actual)
            write_norm(norma, text, final_url, label, sources, override.get("note", ""), norma.get("fonteUrl"))
            success.add(nid)
        except Exception as exc:
            errors.append({"id": nid, "error": f"Câmara: {exc}", "source": source})

    # Reprocessa os atos ICMBio adicionados/corrigidos.
    icmbio_raw = {}
    for nid in ["in-icmbio-5-2016", "in-icmbio-24-2025", "in-icmbio-16-2026"]:
        norma = by_id.get(nid)
        override = overrides.get(nid, {})
        if not norma or not override.get("text_source_url"):
            continue
        try:
            text, final_url, _ = extract_standard(override["text_source_url"])
            icmbio_raw[nid] = text
            write_norm(norma, text, final_url, override.get("text_source_label", norma.get("fonte", "Fonte")), sources, override.get("note", ""), norma.get("fonteUrl"))
            success.add(nid)
        except Exception as exc:
            errors.append({"id": nid, "error": str(exc), "source": override.get("text_source_url")})

    # Consolida a IN ICMBio 24/2025 com a IN 16/2026.
    if "in-icmbio-24-2025" in icmbio_raw and "in-icmbio-16-2026" in icmbio_raw:
        norma = by_id["in-icmbio-24-2025"]
        consolidated = consolidate_in24(icmbio_raw["in-icmbio-24-2025"], icmbio_raw["in-icmbio-16-2026"])
        item = sources.get("in-icmbio-24-2025", {})
        write_norm(
            norma,
            consolidated,
            item.get("textSourceUrl", overrides["in-icmbio-24-2025"]["text_source_url"]),
            "IN ICMBio nº 24/2025 — texto consolidado editorialmente com a IN nº 16/2026",
            sources,
            "Consolidação editorial: redação vigente com alterações da IN ICMBio nº 16/2026; confira também as publicações oficiais indicadas.",
            norma.get("fonteUrl"),
        )

    # Corrige a leitura da IN Idaf 001/2023 em Diário Oficial de duas colunas.
    amendment_text = ""
    in001 = by_id.get("in-idaf-001-2023-barragens")
    direct_pdf = sources.get("in-idaf-001-2023-barragens", {}).get("textSourceUrl")
    if in001 and direct_pdf:
        try:
            amendment_text, final_url = extract_idaf_001_2023(direct_pdf)
            write_norm(in001, amendment_text, final_url, "Idaf — publicação oficial da IN nº 001/2023", sources, "Texto isolado da coluna correspondente ao ato no Diário Oficial.", in001.get("fonteUrl"))
            success.add(in001["id"])
        except Exception as exc:
            errors.append({"id": in001["id"], "error": f"extração multicoluna: {exc}", "source": direct_pdf})

    # Consolida atos estaduais que têm alterações posteriores relevantes.
    patch_decreto_3346(sources)
    if amendment_text and not patch_in20_art32(amendment_text, sources):
        errors.append({"id": "in-idaf-020-2017", "error": "não foi possível consolidar automaticamente o art. 32 com a IN 001/2023", "source": direct_pdf})

    # As IN 008/2014 e 009/2014 são confirmadas por referência institucional, mas
    # a íntegra documental não foi encontrada no acervo atual. Não publicar a notícia como se fosse a norma.
    for nid in ["in-idaf-008-2014-barragens", "in-idaf-009-2014-barragens"]:
        norma = by_id.get(nid)
        if norma:
            write_unavailable(norma, sources, "O Idaf confirma historicamente a existência e a finalidade deste ato, porém o arquivo integral não foi localizado no acervo eletrônico consultado. A página institucional não é usada como substituto do texto normativo.")
            errors.append({"id": nid, "error": "íntegra histórica não localizada; notícia institucional rejeitada como fonte textual", "source": norma.get("fonteUrl")})

    # Reclassifica o relatório conforme o estado efetivo de cada página.
    for norma in normas:
        nid = norma["id"]
        if sources.get(nid, {}).get("available") and (TEXT_DIR / f"{nid}.html").exists():
            success.add(nid)
        elif not any(e.get("id") == nid for e in errors):
            prev = next((e for e in old_report.get("errors", []) if e.get("id") == nid), None)
            if prev:
                errors.append(prev)
            else:
                errors.append({"id": nid, "error": "texto não disponível após consolidação", "source": norma.get("fonteUrl")})

    # Remove erros resolvidos que ainda tenham ficado do relatório anterior.
    unresolved_ids = {e["id"] for e in errors if e["id"] not in success or e["id"] in {"in-idaf-008-2014-barragens", "in-idaf-009-2014-barragens"}}
    final_errors = []
    seen = set()
    for e in errors:
        if e["id"] not in unresolved_ids:
            continue
        key = (e["id"], e.get("error"))
        if key not in seen:
            seen.add(key)
            final_errors.append(e)

    index = rebuild_index(normas)
    save_js_json(ROOT / "generated-index.js", "window.NORM_TEXT_INDEX = ", index)
    save_js_json(ROOT / "generated-sources.js", "window.NORM_SOURCES = ", sources)
    report = {
        "success": sorted(success),
        "errors": final_errors,
        "total_normas": len(normas),
        "total_com_texto": len(success),
        "total_pendentes": len({e["id"] for e in final_errors}),
    }
    (ROOT / "generated-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Enriquecimento concluído: {report['total_com_texto']}/{report['total_normas']} com texto; {report['total_pendentes']} pendentes.")


if __name__ == "__main__":
    main()
