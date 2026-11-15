"""Check documentation coverage and exported contracts without starting services."""
from pathlib import Path
import ast
import csv
import json
import re
import subprocess
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'bi'))
import build_reference_docs as reference
from dashboards import build


def audit():
    tracked = set(filter(None, subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT, text=True,
    ).split('\0')))
    issues = []

    def require(condition, message):
        if not condition:
            issues.append(message)

    catalog = (ROOT / 'docs/FILES_REFERENCE.md').read_text(encoding='utf-8')
    documented = re.findall(r'^### \[([^\]]+)\]\(\.\./[^)]+\)', catalog, re.M)
    require(set(documented) == tracked and len(documented) == len(tracked),
            'File reference must describe every tracked file exactly once')
    require(set(reference.FILES) == tracked,
            'File description dictionary differs from tracked file list')

    folders = {p.as_posix() for name in tracked for p in Path(name).parents if p != Path('.')}
    documented_folders = set(re.findall(r'^\| `([^`]+?)/` \|', catalog, re.M))
    require(folders <= documented_folders, 'Folder descriptions are missing')

    link_count = 0
    for name in sorted(tracked):
        path = ROOT / name
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=name)
        if path.suffix != '.md':
            continue
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            target = target.strip('<>')
            if target.startswith('#') or urlparse(target).scheme:
                continue
            relative = unquote(target.split('#')[0])
            if not relative:
                continue
            destination = (path.parent / relative).resolve()
            require(destination == ROOT or ROOT in destination.parents,
                    f'Link leaves repository: {name}')
            require(destination.exists(), f'Broken file link: {name} -> {relative}')
            link_count += 1

    metadata = json.loads((ROOT / 'docs/schema_reference.json').read_text(encoding='utf-8'))
    database_doc = (ROOT / 'docs/DATABASE_REFERENCE.md').read_text(encoding='utf-8')
    object_names = set()
    column_count = 0
    for key, namespace in [('clickhouse', 'database'), ('postgresql', 'schema')]:
        database = metadata[key]
        for obj in database['objects']:
            name = obj[namespace] + '.' + obj['name']
            object_names.add(name)
            match = re.search(r'^### ' + re.escape(name) + r'\n(.*?)(?=^### |\Z)',
                              database_doc, re.M | re.S)
            require(match is not None, 'Missing database object: ' + name)
            columns = [c for c in database['columns']
                       if c[namespace] == obj[namespace] and c['table'] == obj['name']]
            column_count += len(columns)
            if match:
                documented_columns = re.findall(r'^\| `([^`]+)` \| `([^`]+)`', match[1], re.M)
                require(documented_columns == [(c['name'], c['type']) for c in columns],
                        'Column names/types differ: ' + name)
            for column in columns:
                require(column['name'] in reference.FIELDS,
                        'Missing column explanation: ' + name + '.' + column['name'])
    require(set(re.findall(r'^### ([\w]+\.[\w]+)$', database_doc, re.M)) == object_names,
            'Database object index is incomplete or stale')

    spec = build()
    exported = json.loads((ROOT / 'bi/dashboard_spec.json').read_text(encoding='utf-8'))
    require(spec == exported, 'Dashboard JSON differs from Python specification')
    card_keys = [c['key'] for d in spec for c in d['cards']]
    dashboard_doc = (ROOT / 'docs/DASHBOARD_REFERENCE.md').read_text(encoding='utf-8')
    documented_cards = re.findall(r'^### `([^`]+)`', dashboard_doc, re.M)
    require(documented_cards == card_keys, 'Dashboard reference does not cover every card in order')

    tree = ast.parse((ROOT / 'collector/app/kpi_catalog.py').read_text(encoding='utf-8'))
    kpis = next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'KPI' for t in n.targets))
    with (ROOT / 'docs/KPI_DICTIONARY.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter=';'))
    require([row['Код KPI'] for row in rows] == [k[0] for k in kpis],
            'CSV KPI dictionary differs from source catalog')
    kpi_doc = (ROOT / 'docs/KPI_DICTIONARY.md').read_text(encoding='utf-8')
    for code, name, unit, *_ in kpis:
        require(f'| {code} | {name} | {unit} |' in kpi_doc, 'Missing KPI definition: ' + code)

    example = (ROOT / '.env.example').read_text(encoding='utf-8')
    variables = re.findall(r'^([A-Z][A-Z0-9_]*)=', example, re.M)
    connection_doc = (ROOT / 'docs/CONNECTIONS.md').read_text(encoding='utf-8')
    for variable in variables:
        require(f'| {variable} |' in connection_doc, 'Undocumented environment variable: ' + variable)

    index = (ROOT / 'docs/README.md').read_text(encoding='utf-8')
    for name in tracked:
        if name.startswith('docs/') and name.endswith('.md') and name != 'docs/README.md':
            require('(' + Path(name).name + ')' in index, 'Documentation index omits ' + name)

    if issues:
        raise SystemExit('\n'.join(issues))
    return dict(files=len(tracked), folders=len(folders), database_objects=len(object_names),
                columns=column_count, kpi_definitions=len(kpis), dashboards=len(spec),
                cards=len(card_keys), environment_variables=len(variables), local_links=link_count)


if __name__ == '__main__':
    print('PASS documentation audit: ' + json.dumps(audit(), ensure_ascii=False))
