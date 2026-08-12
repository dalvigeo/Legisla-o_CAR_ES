from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "textos"

KNOWN_BLOCKS = {
    "in-idaf-001-2023-barragens": (
        "O Idaf confirma que a Instrução Normativa nº 001/2023 altera o art. 32 da "
        "Instrução Normativa nº 020/2017. Entretanto, o arquivo oficial está publicado em "
        "página multicoluna do Diário Oficial e sua camada textual mistura trechos de outro "
        "ato administrativo. A transcrição integral permanece bloqueada até que seja possível "
        "reconstituí-la com segurança documental."
    ),
}


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
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def save_js(path: Path, prefix: str, value):
    path.write_text(prefix + json.dumps(value, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


def unavailable_html(norma: dict, url: str, reason: str) -> str:
    return f'''<section class="texto-norma texto-indisponivel" data-norma-id="{norma['id']}">
<div class="notice"><strong>Texto integral temporariamente indisponível.</strong> {reason}</div>
<p><a href="{url}" target="_blank" rel="noopener">Acessar fonte oficial ↗</a></p>
</section>'''


def main():
    normas = load_normas()
    by_id = {n["id"]: n for n in normas}
    sources_path = ROOT / "generated-sources.js"
    index_path = ROOT / "generated-index.js"
    report_path = ROOT / "generated-report.json"

    sources = load_js(sources_path, "window.NORM_SOURCES = ", {})
    index = load_js(index_path, "window.NORM_TEXT_INDEX = ", [])
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}

    blocked = set(report.get("quality_blocked", []))

    for nid, reason in KNOWN_BLOCKS.items():
        norma = by_id.get(nid)
        if not norma:
            continue
        source = sources.get(nid, {})
        # Uma futura transcrição manual explicitamente validada libera o bloqueio.
        if source.get("manualValidated"):
            continue

        official = source.get("officialUrl") or norma.get("fonteUrl", "#")
        (TEXT_DIR / f"{nid}.html").write_text(
            unavailable_html(norma, official, reason), encoding="utf-8"
        )
        sources[nid] = {
            **source,
            "officialUrl": official,
            "available": False,
            "qualityBlocked": True,
            "note": reason,
        }
        index = [item for item in index if item.get("id") != nid]
        blocked.add(nid)

    approved = [
        n["id"] for n in normas
        if n["id"] not in blocked and sources.get(n["id"], {}).get("available")
    ]

    # Mantém apenas ocorrências ainda relevantes no resumo final do relatório.
    unresolved_errors = []
    seen = set()
    for item in report.get("errors", []):
        nid = item.get("id")
        if nid not in blocked:
            continue
        key = (nid, item.get("error", ""))
        if key not in seen:
            seen.add(key)
            unresolved_errors.append(item)

    for nid, reason in KNOWN_BLOCKS.items():
        if nid in blocked:
            key = (nid, "bloqueio final de integridade documental")
            if key not in seen:
                unresolved_errors.append({
                    "id": nid,
                    "error": "bloqueio final de integridade documental",
                    "source": sources.get(nid, {}).get("officialUrl", by_id[nid].get("fonteUrl", "")),
                    "detail": reason,
                })

    report.update({
        "success": sorted(approved),
        "errors": unresolved_errors,
        "quality_blocked": sorted(blocked),
        "total_normas": len(normas),
        "total_com_texto": len(approved),
        "total_pendentes": len(blocked),
    })

    save_js(sources_path, "window.NORM_SOURCES = ", sources)
    save_js(index_path, "window.NORM_TEXT_INDEX = ", index)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guarda final: {len(approved)}/{len(normas)} com texto; {len(blocked)} pendentes.")


if __name__ == "__main__":
    main()
