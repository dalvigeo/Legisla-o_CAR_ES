from __future__ import annotations

import html
import json
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import fitz
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "textos"
OVERRIDES_FILE = ROOT / "source_overrides.json"
USER_AGENT = "LegislaCAR/1.0 (+https://github.com/dalvigeo/LegislaCAR)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})
TIMEOUT = 45


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("º", "").replace("ª", "")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def load_normas() -> list[dict]:
    js = (
        "global.window={};require('./data.js');"
        "process.stdout.write(JSON.stringify(window.NORMAS));"
    )
    proc = subprocess.run(
        ["node", "-e", js], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return json.loads(proc.stdout)


def get(url: str) -> requests.Response:
    response = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def looks_like_document(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".pdf", ".htm", ".html", ".txt", ".doc", ".docx"))


def candidate_score(anchor_text: str, href: str, norma: dict) -> float:
    text = normalize(anchor_text)
    title = normalize(norma.get("titulo"))
    subtitle = normalize(norma.get("subtitulo"))
    number = normalize(norma.get("numero"))
    date = normalize(norma.get("data"))
    score = 0.0

    if number and number in text:
        score += 20
    else:
        num_parts = [p for p in number.split() if len(p) >= 3]
        score += sum(2 for p in num_parts if p in text)

    title_tokens = [t for t in title.split() if len(t) > 3]
    subtitle_tokens = [t for t in subtitle.split() if len(t) > 4]
    score += sum(1.5 for t in title_tokens if t in text)
    score += sum(0.7 for t in subtitle_tokens if t in text)

    year = re.findall(r"\b(?:19|20)\d{2}\b", date + " " + number)
    if year and any(y in text for y in year):
        score += 6

    if "baixar" in text or href.lower().endswith(".pdf"):
        score += 2
    if "media/idaf" in href.lower():
        score += 2
    return score


def resolve_from_listing(url: str, norma: dict) -> str | None:
    response = get(url)
    soup = BeautifulSoup(response.content, "lxml")
    candidates: list[tuple[float, str, str]] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(response.url, a.get("href"))
        text = a.get_text(" ", strip=True)
        if not href.startswith("http"):
            continue
        score = candidate_score(text, href, norma)
        if score > 5:
            candidates.append((score, href, text))
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0], reverse=True)
    return candidates[0][1]


def resolve_official_url(norma: dict) -> str:
    url = norma.get("fonteUrl", "")
    if not url:
        return ""
    if looks_like_document(url) and "GrupodeArquivos" not in url and "legislacao-idaf" not in url and "normas-de-procedimentos" not in url:
        return url
    try:
        resolved = resolve_from_listing(url, norma)
        return resolved or url
    except Exception:
        return url


def detect_content_type(response: requests.Response) -> str:
    ctype = response.headers.get("Content-Type", "").lower()
    if "pdf" in ctype or response.content[:5] == b"%PDF-":
        return "pdf"
    return "html"


def strip_obsolete_markup(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["strike", "s", "del"]):
        tag.decompose()
    for tag in soup.find_all(style=True):
        style = str(tag.get("style", "")).lower().replace(" ", "")
        if "line-through" in style:
            tag.decompose()


def extract_html_text(url: str) -> tuple[str, str]:
    response = get(url)
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    soup = BeautifulSoup(response.text, "lxml")
    strip_obsolete_markup(soup)
    for tag in soup(["script", "style", "noscript", "svg", "form", "button", "nav", "footer"]):
        tag.decompose()

    # Fontes jurídicas mais comuns: Planalto usa muitos <p>; sites de consolidação usam article/main.
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks: list[str] = []
    seen: set[str] = set()
    for tag in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td"], recursive=True):
        # Evita duplicar conteúdo de tabelas ou containers aninhados.
        if tag.find_parent(["p", "li"]):
            continue
        text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
        if not text or len(text) < 2:
            continue
        n = normalize(text)
        if n in seen:
            continue
        seen.add(n)
        blocks.append(text)

    # Fallback para páginas com estrutura incomum.
    if len(" ".join(blocks)) < 500:
        raw = root.get_text("\n", strip=True)
        blocks = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines() if line.strip()]

    text = "\n".join(blocks)
    return clean_extracted_text(text), response.url


def extract_pdf_text(url: str) -> tuple[str, str]:
    response = get(url)
    doc = fitz.open(stream=response.content, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        text = page.get_text("text", sort=True)
        if text.strip():
            pages.append(text)
    joined = "\n".join(pages)
    return clean_extracted_text(joined), response.url


def clean_extracted_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Une hifenização artificial de quebra de linha em PDFs.
    text = re.sub(r"([A-Za-zÀ-ÿ])-\n([a-zà-ÿ])", r"\1\2", text)
    return text.strip()


def extract_text(url: str) -> tuple[str, str, str]:
    response = get(url)
    kind = detect_content_type(response)
    # Reutiliza a URL final para evitar resolver duas vezes.
    final_url = response.url
    if kind == "pdf":
        doc = fitz.open(stream=response.content, filetype="pdf")
        pages = [page.get_text("text", sort=True) for page in doc]
        text = clean_extracted_text("\n".join(pages))
        return text, final_url, "PDF"

    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    soup = BeautifulSoup(response.text, "lxml")
    strip_obsolete_markup(soup)
    for tag in soup(["script", "style", "noscript", "svg", "form", "button", "nav", "footer"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks = []
    seen = set()
    for tag in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td"], recursive=True):
        if tag.find_parent(["p", "li"]):
            continue
        value = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
        if not value:
            continue
        key = normalize(value)
        if key and key not in seen:
            seen.add(key)
            blocks.append(value)
    if len(" ".join(blocks)) < 500:
        blocks = [re.sub(r"\s+", " ", x).strip() for x in root.get_text("\n", strip=True).splitlines() if x.strip()]
    return clean_extracted_text("\n".join(blocks)), final_url, "HTML"


def remove_site_chrome(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    useful = []
    started = False
    start_patterns = [
        r"^(LEI|DECRETO|MEDIDA PROVIS[ÓO]RIA|RESOLU[ÇC][ÃA]O|INSTRU[ÇC][ÃA]O|NORMA DE PROCEDIMENTO)",
        r"^O PRESIDENTE",
        r"^A PRESIDENTA",
        r"^O GOVERNADOR",
        r"^O DIRETOR",
        r"^Art\.\s*1",
    ]
    for line in lines:
        if not line:
            if useful and useful[-1] != "":
                useful.append("")
            continue
        if not started and any(re.search(p, line, re.I) for p in start_patterns):
            started = True
        if started:
            # Remove rodapés recorrentes de agregadores sem apagar conteúdo normativo.
            if re.match(r"^(Parte inferior do formul|publica[cç][aã]o no sistema:)", line, re.I):
                continue
            useful.append(line)
    if not useful:
        return text
    return "\n".join(useful).strip()


def extract_article_block(text: str, article: str) -> str | None:
    pattern = re.compile(
        rf"(?ims)^\s*Art\.?\s*{re.escape(article)}(?:º|o|°)?\b.*?(?=^\s*Art\.?\s*\d+(?:º|o|°)?\b|\Z)"
    )
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def replace_article(base_text: str, article: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?ims)^\s*Art\.?\s*{re.escape(article)}(?:º|o|°)?\b.*?(?=^\s*Art\.?\s*\d+(?:º|o|°)?\b|\Z)"
    )
    if pattern.search(base_text):
        return pattern.sub(replacement.strip() + "\n", base_text, count=1)
    return base_text + "\n\n" + replacement.strip()


def is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if re.match(r"^(CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O|T[ÍI]TULO|LIVRO|ANEXO)\b", stripped, re.I):
        return True
    letters = [c for c in stripped if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.86 and len(letters) > 5


def split_paragraphs(text: str) -> list[str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current = ""

    structural = re.compile(
        r"^(Art\.?\s*\d+[A-Za-z-]*(?:º|o|°)?\b|§\s*\d+|Par[aá]grafo [uú]nico\b|[IVXLCDM]+\s*[-–—.]\s+|[a-z]\)\s+|CAP[ÍI]TULO\b|SE[ÇC][ÃA]O\b|SUBSE[ÇC][ÃA]O\b|ANEXO\b)",
        re.I,
    )

    def flush():
        nonlocal current
        if current.strip():
            paragraphs.append(current.strip())
        current = ""

    for line in lines:
        if not line:
            flush()
            continue
        if structural.match(line) or is_heading(line):
            flush()
            paragraphs.append(line)
            continue
        if not current:
            current = line
        else:
            # Une linhas quebradas pelo PDF, preservando sentenças e estruturas.
            current += " " + line
    flush()
    return paragraphs


def slug_article(paragraph: str) -> str | None:
    match = re.match(r"^Art\.?\s*(\d+[A-Za-z-]*)", paragraph, re.I)
    return f"art-{match.group(1).lower()}" if match else None


def format_html(text: str, norma: dict, source_url: str, source_label: str) -> str:
    paragraphs = split_paragraphs(text)
    out = [
        '<section class="texto-norma" data-norma-id="{}">'.format(html.escape(norma["id"])),
        '<div class="texto-norma-toolbar">',
        '<strong>Texto da norma</strong>',
        '<span>Transcrição formatada a partir da fonte indicada.</span>',
        '</div>',
    ]
    for p in paragraphs:
        safe = html.escape(p)
        art_id = slug_article(p)
        if is_heading(p):
            out.append(f'<h2 class="norm-heading">{safe}</h2>')
        elif art_id:
            out.append(f'<p class="norm-artigo" id="{art_id}">{safe}</p>')
        elif re.match(r"^(§\s*\d+|Par[aá]grafo [uú]nico)", p, re.I):
            out.append(f'<p class="norm-paragrafo">{safe}</p>')
        elif re.match(r"^[IVXLCDM]+\s*[-–—.]\s+", p):
            out.append(f'<p class="norm-inciso">{safe}</p>')
        elif re.match(r"^[a-z]\)\s+", p, re.I):
            out.append(f'<p class="norm-alinea">{safe}</p>')
        else:
            out.append(f'<p>{safe}</p>')
    out.extend([
        '<div class="texto-norma-fonte">',
        '<span>Fonte usada nesta transcrição:</span> ',
        f'<a href="{html.escape(source_url)}" target="_blank" rel="noopener">{html.escape(source_label)} ↗</a>',
        '</div>',
        '</section>',
    ])
    return "\n".join(out)


def compact_for_search(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    # Evita índices excessivamente pesados, preservando conteúdo integral até limite muito alto.
    return text[:450000]


def main() -> None:
    normas = load_normas()
    overrides = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")) if OVERRIDES_FILE.exists() else {}
    TEXT_DIR.mkdir(exist_ok=True)

    results: dict[str, dict] = {}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "success": [], "errors": []}

    # Primeiro resolve e extrai cada ato.
    for norma in normas:
        nid = norma["id"]
        override = overrides.get(nid, {})
        official_url = resolve_official_url(norma)
        text_source_url = override.get("text_source_url") or official_url or norma.get("fonteUrl", "")
        text_source_label = override.get("text_source_label") or norma.get("fonte", "Fonte indicada")
        try:
            raw_text, final_url, source_kind = extract_text(text_source_url)
            raw_text = remove_site_chrome(raw_text)
            if len(raw_text) < 180:
                raise RuntimeError("texto extraído muito curto")
            results[nid] = {
                "norma": norma,
                "text": raw_text,
                "official_url": official_url or norma.get("fonteUrl", ""),
                "text_source_url": final_url,
                "text_source_label": text_source_label,
                "source_kind": source_kind,
                "note": override.get("note", ""),
            }
        except Exception as exc:
            report["errors"].append({"id": nid, "error": str(exc), "source": text_source_url})

    # Consolida alterações pontuais configuradas.
    for nid, override in overrides.items():
        if nid not in results:
            continue
        amendment_id = override.get("merge_amendment_id")
        article = str(override.get("merge_article", ""))
        if amendment_id and article and amendment_id in results:
            replacement = extract_article_block(results[amendment_id]["text"], article)
            if replacement:
                results[nid]["text"] = replace_article(results[nid]["text"], article, replacement)
                results[nid]["note"] = (results[nid].get("note", "") + " Alteração incorporada editorialmente.").strip()
            else:
                report["errors"].append({"id": nid, "error": f"não foi possível localizar o art. {article} na norma alteradora", "source": results[amendment_id]["text_source_url"]})

    search_index = []
    sources = {}
    for norma in normas:
        nid = norma["id"]
        item = results.get(nid)
        if not item:
            # Mantém uma página explícita para falhas de coleta, sem inventar conteúdo.
            error = next((e for e in report["errors"] if e["id"] == nid), None)
            message = html.escape(error["error"] if error else "Fonte não localizada")
            fallback = norma.get("fonteUrl", "#")
            generated = (
                '<section class="texto-norma texto-indisponivel">'
                '<div class="notice"><strong>Texto ainda não transcrito automaticamente.</strong> '
                f'{message}. Consulte a fonte cadastrada para esta norma.</div>'
                f'<p><a href="{html.escape(fallback)}" target="_blank" rel="noopener">Acessar fonte cadastrada ↗</a></p>'
                '</section>'
            )
            (TEXT_DIR / f"{nid}.html").write_text(generated, encoding="utf-8")
            sources[nid] = {
                "officialUrl": fallback,
                "textSourceUrl": fallback,
                "textSourceLabel": norma.get("fonte", "Fonte cadastrada"),
                "available": False,
            }
            continue

        formatted = format_html(item["text"], norma, item["text_source_url"], item["text_source_label"])
        (TEXT_DIR / f"{nid}.html").write_text(formatted, encoding="utf-8")
        sources[nid] = {
            "officialUrl": item["official_url"],
            "textSourceUrl": item["text_source_url"],
            "textSourceLabel": item["text_source_label"],
            "sourceKind": item["source_kind"],
            "available": True,
            "note": item.get("note", ""),
        }
        search_index.append({"id": nid, "text": compact_for_search(item["text"])})
        report["success"].append(nid)

    (ROOT / "generated-index.js").write_text(
        "window.NORM_TEXT_INDEX = " + json.dumps(search_index, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    (ROOT / "generated-sources.js").write_text(
        "window.NORM_SOURCES = " + json.dumps(sources, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    (ROOT / "generated-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Geradas {len(report['success'])}/{len(normas)} normas; {len(report['errors'])} ocorrências registradas.")


if __name__ == "__main__":
    main()
