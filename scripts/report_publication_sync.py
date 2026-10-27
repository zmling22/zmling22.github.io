#!/usr/bin/env python3
"""Write sync diagnostics to the Actions summary without masking a failure."""
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / '.local/scholar-sync-status.json'
if path.exists():
    status = json.loads(path.read_text(encoding='utf-8'))
    lines = ['## Publication sync', '',
             'Result: ' + ('success' if status.get('success') else 'failed; previous data retained')]
    if status.get('success'):
        lines += [f"Source timestamp: {status['updated']}",
                  f"Publications: {status['publications']}"]
    if status.get('error'):
        lines.append('Error: ' + status['error'])
    if status.get('images'):
        lines += ['', '### PDF figure results', '', '```json',
                  json.dumps(status['images'], ensure_ascii=False, indent=2), '```']
else:
    lines = ['## Publication sync', '', 'Sync did not finish; inspect the failed workflow step.']
summary = '\n\n'.join(lines) + '\n'
print(summary)
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
        handle.write(summary)
