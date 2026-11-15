"""Run offline application and BI tests without external notifications."""
from pathlib import Path
import subprocess,sys,os
ROOT=Path(__file__).resolve().parents[1]

def main():
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join([str(ROOT/'collector'),env.get('PYTHONPATH','')])
    env['PYTHONDONTWRITEBYTECODE']='1'
    for folder in ('collector/tests','bi'):
        subprocess.run([sys.executable,'-m','unittest','discover','-s',folder,'-p','test_*.py','-v'],cwd=ROOT,env=env,check=True)
    print('PASS application and dashboard tests; no live messages sent')

if __name__=='__main__':main()
