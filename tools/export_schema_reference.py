"""Read schema metadata only; no application rows or credentials are exported."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[1]

def run(service,code):
    result=subprocess.run(['docker','compose','run','--rm','--no-deps',service,'python','-c',code],cwd=ROOT,text=True,encoding='utf-8',capture_output=True,check=True)
    return json.loads(result.stdout)

def main():
    ch=run('analytics',"""import json
from app.retention_clickhouse import ch
print(json.dumps({'objects':ch("SELECT database,name,engine,sorting_key,partition_key,create_table_query FROM system.tables WHERE database IN ('monitoring','analytics') ORDER BY database,name FORMAT JSONEachRow"),'columns':ch("SELECT database,table,name,type,default_kind,default_expression FROM system.columns WHERE database IN ('monitoring','analytics') ORDER BY database,table,position FORMAT JSONEachRow")}))""")
    pg=run('alerts',"""import json,os,psycopg
from psycopg.rows import dict_row
with psycopg.connect(os.environ['POSTGRES_DSN'],row_factory=dict_row) as conn:
 objects=conn.execute("SELECT table_schema AS schema,table_name AS name,table_type AS kind FROM information_schema.tables WHERE table_schema IN ('public','reporting') ORDER BY 1,2").fetchall()
 columns=conn.execute("SELECT table_schema AS schema,table_name AS table,column_name AS name,data_type AS type,is_nullable,column_default FROM information_schema.columns WHERE table_schema IN ('public','reporting') ORDER BY table_schema,table_name,ordinal_position").fetchall()
 constraints=conn.execute("SELECT n.nspname AS schema,c.relname AS table,con.conname AS name,pg_get_constraintdef(con.oid) AS definition FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','reporting') ORDER BY 1,2,3").fetchall()
 views=conn.execute("SELECT schemaname AS schema,viewname AS name,definition FROM pg_views WHERE schemaname IN ('public','reporting') ORDER BY 1,2").fetchall()
 print(json.dumps(dict(objects=objects,columns=columns,constraints=constraints,views=views)))""")
    destination=ROOT/'docs/schema_reference.json'
    destination.write_text(json.dumps({'clickhouse':ch,'postgresql':pg},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Exported metadata:',len(ch['objects']),'ClickHouse objects;',len(pg['objects']),'PostgreSQL objects')

if __name__=='__main__':main()
