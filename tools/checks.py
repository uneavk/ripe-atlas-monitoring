"""Run focused checks without sending external notifications."""
from pathlib import Path
import argparse,ast,csv,io,json,os,re,subprocess,sys,zipfile
from urllib.parse import unquote,urlparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'bi'))
import docs as reference
from dashboards import build
PATTERNS=[
    ('telegram_token',re.compile(r'\b\d{7,12}:[A-Za-z0-9_-]{30,}\b')),
    ('github_token',re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})\b')),
    ('private_key',re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('local_profile_path',re.compile(r'(?:[A-Za-z]:\\Users\\|[A-Za-z]:/Users/)',re.I)),
]
PRIVATE_SUFFIXES={'.db','.dump','.sqlite','.sqlite3','.log','.pem','.key','.zip','.gz','.pyc'}

def inspect_file(name):
    path=ROOT/name
    if (any(part in {'.secrets','backups','data','volumes','state','logs','.venv','__pycache__'} for part in path.relative_to(ROOT).parts)
        or (path.name.startswith('.env') and path.name!='.env.example') or path.suffix.lower() in PRIVATE_SUFFIXES):
        return ['runtime_or_private_file']
    raw=path.read_bytes()
    # Only these reviewed hand-in documents are accepted as new binary types.
    # Visible PDF/image content still requires manual review, just like screenshots.
    if name=='artifacts/handin/RIPE_Atlas_Report.pdf':
        return [] if raw.startswith(b'%PDF-') and b'%%EOF' in raw[-2048:] and len(raw)>10000 else ['invalid_pdf']
    if name=='artifacts/handin/RIPE_Atlas_Defense.pptx':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as package:
                names=set(package.namelist())
                required={'[Content_Types].xml','_rels/.rels','ppt/presentation.xml'}
                if not required<=names:return ['invalid_pptx']
                if sum(info.file_size for info in package.infolist())>50*1024*1024:return ['oversize_pptx']
                if any(n.startswith('ppt/embeddings/') or n.lower().endswith('vbaproject.bin') for n in names):
                    return ['unexpected_pptx_attachment']
                issues=[]
                for part in names:
                    if part.endswith(('.xml','.rels')):
                        xml=package.read(part).decode('utf-8-sig')
                        issues.extend(label for label,pattern in PATTERNS if pattern.search(xml))
                return sorted(set(issues))
        except (OSError,UnicodeError,zipfile.BadZipFile):return ['invalid_pptx']
    if path.suffix.lower()=='.png':
        return [] if raw.startswith(b'\x89PNG\r\n\x1a\n') else ['invalid_png']
    if path.suffix.lower() in {'.jpg','.jpeg'}:
        return [] if raw.startswith(b'\xff\xd8\xff') and raw.endswith(b'\xff\xd9') else ['invalid_jpeg']
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:return ['unexpected_binary_file']
    issues=[label for label,pattern in PATTERNS if pattern.search(text)]
    if path.suffix.lower()=='.json':
        try:
            def walk(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key.lower() in {'password','data_password','token','api_key','access_token','client_secret'} and isinstance(item,str) and item and not item.startswith(('replace_with_','${')):
                            issues.append('credential_literal')
                        walk(item)
                elif isinstance(value,list):
                    for item in value:walk(item)
            walk(json.loads(text))
        except json.JSONDecodeError:issues.append('invalid_json')
    return issues

def publication():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    problems=[(name,label) for name in filter(None,paths) for label in inspect_file(name)]
    if problems:
        for name,label in problems:print(name,label)
        raise SystemExit('Publication check failed')
    print('PASS: tracked files contain no detected credentials, runtime files or local profile paths.')
    print('PNG/JPEG/PDF signatures and the approved PPTX package/XML are checked; visible contents require visual review.')

def audit():
    tracked = set(filter(None, subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT, text=True,
    ).split('\0')))
    issues = []

    def require(condition, message):
        if not condition:
            issues.append(message)

    catalog = (ROOT / 'docs/FILES.md').read_text(encoding='utf-8')
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
    database_doc = (ROOT / 'docs/DATABASE.md').read_text(encoding='utf-8')
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
    dashboard_doc = (ROOT / 'docs/ANALYTICS.md').read_text(encoding='utf-8')
    documented_cards = re.findall(r'^#### `([^`]+)`', dashboard_doc, re.M)
    require(documented_cards == card_keys, 'Dashboard reference does not cover every card in order')

    tree = ast.parse((ROOT / 'collector/app/kpi_catalog.py').read_text(encoding='utf-8'))
    kpis = next(ast.literal_eval(n.value) for n in tree.body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'KPI' for t in n.targets))
    with (ROOT / 'docs/KPI_DICTIONARY.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter=';'))
    require([row['Код KPI'] for row in rows] == [k[0] for k in kpis],
            'CSV KPI dictionary differs from source catalog')
    kpi_doc = (ROOT / 'docs/ANALYTICS.md').read_text(encoding='utf-8')
    for code, name, unit, *_ in kpis:
        require(f'| {code} | {name} | {unit} |' in kpi_doc, 'Missing KPI definition: ' + code)

    example = (ROOT / '.env.example').read_text(encoding='utf-8')
    variables = re.findall(r'^([A-Z][A-Z0-9_]*)=', example, re.M)
    connection_doc = (ROOT / 'docs/SETUP.md').read_text(encoding='utf-8')
    for variable in variables:
        require(f'| {variable} |' in connection_doc, 'Undocumented environment variable: ' + variable)

    index = (ROOT / 'README.md').read_text(encoding='utf-8')
    for name in tracked:
        if name.startswith('docs/') and name.endswith('.md'):
            require('(' + name + ')' in index, 'Documentation index omits ' + name)

    if issues:
        raise SystemExit('\n'.join(issues))
    return dict(files=len(tracked), folders=len(folders), database_objects=len(object_names),
                columns=column_count, kpi_definitions=len(kpis), dashboards=len(spec),
                cards=len(card_keys), environment_variables=len(variables), local_links=link_count)

def unit():
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join([str(ROOT/'collector'),env.get('PYTHONPATH','')])
    env['PYTHONDONTWRITEBYTECODE']='1'
    for folder in ('collector/tests','bi'):
        subprocess.run([sys.executable,'-m','unittest','discover','-s',folder,'-p','test_*.py','-v'],cwd=ROOT,env=env,check=True)
    print('PASS application and dashboard tests; no live messages sent')

def main():
    parser=argparse.ArgumentParser(description='Run offline project checks')
    parser.add_argument('--unit',action='store_true',help='Run application and BI unit tests')
    parser.add_argument('--docs',action='store_true',help='Verify complete documentation coverage')
    parser.add_argument('--publication',action='store_true',help='Check files tracked by Git')
    args=parser.parse_args()
    all_checks=not(args.unit or args.docs or args.publication)
    if all_checks or args.unit:unit()
    if all_checks or args.docs:print('PASS documentation audit: '+json.dumps(audit(),ensure_ascii=False))
    if all_checks or args.publication:publication()

if __name__=='__main__':main()
