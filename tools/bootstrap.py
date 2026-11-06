"""First launch and idempotent reporting/NiFi configuration."""
from pathlib import Path
import secrets,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]

def run(*arguments):
    print('>', ' '.join(arguments),flush=True)
    subprocess.run(arguments,cwd=ROOT,check=True)

def environment():
    path=ROOT/'.env'
    if not path.exists():
        text=(ROOT/'.env.example').read_text(encoding='utf-8')
        for old in ('replace_with_random_hex_password','replace_with_different_random_hex_password','replace_with_random_password_at_least_12_characters'):
            text=text.replace(old,secrets.token_hex(20))
        path.write_text(text,encoding='utf-8')
        print('Created .env with generated local passwords. Keep this file private.',flush=True)
    text=path.read_text(encoding='utf-8-sig')
    if 'replace_with_' in text:raise SystemExit('Replace placeholder passwords in .env before starting.')
    (ROOT/'.secrets/telegram').mkdir(parents=True,exist_ok=True)

def main():
    environment()
    run('docker','compose','config','--quiet')
    run('docker','compose','build','collector')
    run('docker','compose','up','-d','--no-build')
    run(sys.executable,str(ROOT/'nifi/build_pipeline.py'))
    for module in ('install_kpi','analytics_views'):
        run('docker','compose','exec','-T','analytics','python','-m','app.'+module)
    run('docker','compose','exec','-T','alerts','python','-m','app.operational_views')
    run('docker','compose','ps')
    print('Ready. See README.md and docs/CONNECTIONS.md. Fresh samples usually appear within several minutes.',flush=True)

if __name__=='__main__':main()
