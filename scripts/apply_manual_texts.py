from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / 'manual_texts'
TEXT_DIR = ROOT / 'textos'

import sys
sys.path.insert(0, str(ROOT / 'scripts'))
import build_legislation as base


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


def main():
    normas = {n['id']: n for n in load_normas()}
    sources_path = ROOT / 'generated-sources.js'
    sources = load_js(sources_path, 'window.NORM_SOURCES = ', {})
    applied = []

    for path in sorted(MANUAL.glob('*.txt')):
        nid = path.stem
        norma = normas.get(nid)
        if not norma:
            continue
        text = path.read_text(encoding='utf-8').strip()
        if not text:
            continue

        existing = sources.get(nid, {})
        official = existing.get('officialUrl') or norma.get('fonteUrl', '')
        text_source = existing.get('textSourceUrl') or official
        label = existing.get('textSourceLabel') or norma.get('fonte', 'Fonte oficial')

        formatted = base.format_html(
            text,
            norma,
            text_source,
            label + ' — transcrição validada visualmente'
        )
        (TEXT_DIR / f'{nid}.html').write_text(formatted, encoding='utf-8')
        sources[nid] = {
            **existing,
            'officialUrl': official,
            'textSourceUrl': text_source,
            'textSourceLabel': label + ' — transcrição validada visualmente',
            'available': True,
            'manualValidated': True,
            'qualityBlocked': False,
            'note': (existing.get('note', '') + ' Texto transcrito e conferido visualmente a partir da publicação-fonte.').strip()
        }
        applied.append(nid)

    save_js(sources_path, 'window.NORM_SOURCES = ', sources)
    print(f'Transcrições manuais aplicadas: {len(applied)}' + (f" ({', '.join(applied)})" if applied else ''))


if __name__ == '__main__':
    main()
