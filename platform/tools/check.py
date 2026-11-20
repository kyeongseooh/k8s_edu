"""Offline platform materials check. No credentials, kubectl apply or API calls."""
import argparse
import ast
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, unquote

import yaml

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gitops', type=Path, help='also render the separate GitOps checkout')
parser.add_argument('--schema', type=Path, help='optional saved Kubernetes OpenAPI v2 JSON (requires jsonschema)')
args = parser.parse_args()
if args.schema and not args.gitops:
    parser.error('--schema requires --gitops')

docs = sorted(root.rglob('*.md'))
links = blocks = 0
for p in docs:
    text = p.read_text(encoding='utf-8')
    prose = re.sub(r'^```[^\n]*\n.*?^```[ \t]*$', '', text, flags=re.M | re.S)
    for link in re.findall(r'\]\(([^)\s]+)\)', prose):
        uri = urlsplit(link)
        if uri.scheme or uri.netloc or not uri.path:
            continue
        if not (p.parent / unquote(uri.path)).exists():
            raise ValueError(f'{p.name}: missing {link}')
        links += 1
    for code in re.findall(r'^```bash[ \t]*\n(.*?)^```[ \t]*$', text, re.M | re.S):
        subprocess.run(['bash', '-n'], input=code.encode(), check=True)
        blocks += 1
for p in (root / 'examples').rglob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
print(f'{len(docs)} platform documents; {links} local links; {blocks} Bash blocks')

if args.gitops:
    g = args.gitops.resolve()
    objs = list(yaml.safe_load_all(subprocess.check_output(['kubectl', 'kustomize', str(g / 'clusters/training')])))
    if any(o['metadata'].get('namespace') != 'edu-platform-lab' for o in objs if o['kind'] != 'Namespace'):
        raise ValueError('namespace mismatch')
    maps = {o['metadata']['name'] for o in objs if o['kind'] == 'ConfigMap'}
    pod = next(o for o in objs if o['kind'] == 'Deployment' and o['metadata']['name'] == 'edu-airflow')['spec']['template']['spec']
    dag = next(v['configMap']['name'] for v in pod['volumes'] if v['name'] == 'dags')
    image = next(e['valueFrom']['configMapKeyRef']['name'] for e in pod['containers'][0]['env'] if e['name'] == 'TASK_IMAGE')
    if not ({dag, image} <= maps and dag.startswith('edu-dags-') and image.startswith('task-settings-')):
        raise ValueError('generated ConfigMap references are stale')
    print(f'{len(objs)} GitOps objects; DAG and task digest references match')
    if args.schema:
        from jsonschema import Draft4Validator
        definitions = json.loads(args.schema.read_text())['definitions']
        gvks = {(v['group'], v['version'], v['kind']): n for n, s in definitions.items() for v in s.get('x-kubernetes-group-version-kind', [])}
        objs.extend(yaml.safe_load(p.read_text()) for p in sorted((g / 'bootstrap').glob('*.yaml')))
        objs.extend(yaml.safe_load_all((root / 'examples/oidc/pod-reader.yaml').read_text()))
        for o in objs:
            group, _, version = o['apiVersion'].rpartition('/')
            name = gvks[(group, version, o['kind'])]
            Draft4Validator({'definitions': definitions, '$ref': '#/definitions/' + name}).validate(o)
        print(f'{len(objs)} objects validated against supplied schema (not an admission/sync test)')
