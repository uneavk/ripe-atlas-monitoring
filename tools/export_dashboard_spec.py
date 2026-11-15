"""Export portable dashboard definitions without credentials or local IDs."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bi'))
from dashboards import build

def main():
    (ROOT/'bi/dashboard_spec.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Exported 3 dashboard definitions without credentials')

if __name__=='__main__':main()
