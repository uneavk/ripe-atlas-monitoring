"""Check tracked files before publishing. Reports file paths, never secret values."""
from pathlib import Path
import re,subprocess
ROOT=Path(__file__).resolve().parents[1]
PATTERNS=[
    ('telegram_token',re.compile(r'\b\d{7,12}:[A-Za-z0-9_-]{30,}\b')),
    ('github_token',re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})\b')),
    ('private_key',re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('local_profile_path',re.compile(r'(?:[A-Za-z]:\\Users\\|[A-Za-z]:/Users/)',re.I)),
]

def main():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    problems=[]
    for name in filter(None,paths):
        path=ROOT/name
        if (name.startswith(('.secrets/','backups/')) or name=='.env' or path.suffix in ('.db','.dump','.sqlite','.log')):
            problems.append((name,'runtime_or_private_file'));continue
        text=path.read_text(encoding='utf-8-sig')
        for label,pattern in PATTERNS:
            if pattern.search(text):problems.append((name,label))
    if problems:
        for name,label in problems:print(name,label)
        raise SystemExit('Publication check failed')
    print('PASS: tracked files contain no detected tokens, private keys, runtime databases or local profile paths.')

if __name__=='__main__':main()
