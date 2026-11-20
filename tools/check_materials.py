"""Offline sanity check for editors; does not contact Kubernetes or execute lessons."""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
errors = []
docs = ([ROOT / 'README.md'] + sorted((ROOT / 'docs').glob('*.md'))
        + [ROOT / 'platform' / 'README.md'] + sorted((ROOT / 'platform' / 'docs').glob('*.md')))
examples = sorted((ROOT / 'examples').rglob('*.yaml')) + sorted(
    p for p in (ROOT / 'platform').rglob('*.yaml') if not p.name.startswith('values'))  # Helm values are not objects
links = blocks = objects = 0

for doc in docs:
    text = doc.read_text(encoding='utf-8')
    # Ignore example code when checking Markdown links.
    prose = re.sub(r'^```[^\n]*\n.*?^```[ \t]*$', '', text, flags=re.M | re.S)
    for ref in re.findall(r'\]\(([^)\s]+)\)', prose):
        uri = urlsplit(ref)
        if uri.scheme or uri.netloc or not uri.path:
            continue
        links += 1
        if not (doc.parent / unquote(uri.path)).exists():
            errors.append(f'{doc.name}: no link target: {ref}')
    for block in re.findall(r'^```bash[ \t]*\n(.*?)^```[ \t]*$', text, re.M | re.S):
        blocks += 1
        result = subprocess.run(['bash', '-n'], input=block.encode(), stderr=subprocess.PIPE)
        if result.returncode:
            errors.append(f'{doc.name}: {result.stderr.decode().strip()}')

for path in examples:
    try:
        for obj in yaml.safe_load_all(path.read_text(encoding='utf-8')):
            if path.name.endswith('.patch.yaml') and isinstance(obj, dict) and obj.get('spec'):
                continue  # Partial merge patch, not an object to apply on its own.
            if not isinstance(obj, dict) or not all(obj.get(k) for k in ('apiVersion', 'kind', 'metadata')):
                errors.append(f'{path.name}: incomplete Kubernetes object')
                continue
            objects += 1
            if obj['metadata'].get('namespace') and 'platform' not in path.parts:
                errors.append(f'{path.name}: metadata.namespace overrides the learner’s namespace')
    except yaml.YAMLError as exc:
        errors.append(f'{path.name}: {exc}')

print(f'{len(docs)} Markdown files; {links} local links; {blocks} Bash blocks; '
      f'{len(examples)} YAML files / {objects} objects')
for error in errors:
    print(error, file=sys.stderr)
sys.exit(bool(errors))
