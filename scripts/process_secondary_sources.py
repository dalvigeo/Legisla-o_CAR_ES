from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_legislation as base

TEXT_DIR = ROOT / 'textos'
SOURCES_CONFIG = ROOT / 'secondary_sources.json'


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
    config = json.loads(SOURCES_CONFIG.read_text(encoding='utf-8'))
    sources_path = ROOT / 'generated-sources.js'
    sources = load_js(sources_path, 'window.NORM_SOURCES = ', {})
    report_path = ROOT / 'generated-report.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'errors': []}
    errors = list(report.get('errors', []))
    successes = set(report.get('success', []))

    for nid, source_cfg in config.items():
        norma = normas.get(nid)
        if not norma:
            continue
        try:
            text, final_url, kind = base.extract_text(source_cfg['url'])
            text = base.remove_site_chrome(text)
            if len(text) < 180:
                raise RuntimeError('texto extraído muito curto')
            formatted = base.format_html(text, norma, final_url, source_cfg['label'])
            (TEXT_DIR / f'{nid}.html').write_text(formatted, encoding='utf-8')
            previous = sources.get(nid, {})
            sources[nid] = {
                **previous,
                'officialUrl': previous.get('officialUrl') or norma.get('fonteUrl', ''),
                'textSourceUrl': final_url,
                'textSourceLabel': source_cfg['label'],
                'sourceKind': kind,
                'available': True,
                'qualityBlocked': False,
                'note': source_cfg.get('note', '')
            }
            successes.add(nid)
        except Exception as exc:
            errors.append({'id': nid, 'error': 'fonte alternativa: ' + str(exc), 'source': source_cfg['url']})

    report['success'] = sorted(successes)
    report['errors'] = errors
    save_js(sources_path, 'window.NORM_SOURCES = ', sources)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Fontes alternativas processadas: {len(config)}')


if __name__ == '__main__':
    main()
