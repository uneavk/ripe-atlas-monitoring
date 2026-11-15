"""Check tracked publication files. Print file paths and labels, never values."""
from pathlib import Path
import json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
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

def main():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    problems=[(name,label) for name in filter(None,paths) for label in inspect_file(name)]
    if problems:
        for name,label in problems:print(name,label)
        raise SystemExit('Publication check failed')
    print('PASS: tracked files contain no detected credentials, runtime files or local profile paths.')
    print('PNG/JPEG files are signature-checked; their visible contents require visual review.')

if __name__=='__main__':main()
