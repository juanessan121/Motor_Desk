"""Prepara pruebas Compose con secretos aleatorios y un proyecto independiente."""
import argparse
import json
from pathlib import Path
import re
import secrets
parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--project', required=True)
parser.add_argument('--image', required=True)
args = parser.parse_args()
if not re.fullmatch(r'motordesk-test-[a-z0-9-]+', args.project):
    parser.error('El proyecto debe comenzar por motordesk-test- y usar letras minúsculas, números o guiones')
args.directory.mkdir(parents=True, exist_ok=False)
(args.directory/'project.txt').write_text(args.project,encoding='utf-8')
(args.directory/'test.env').write_text('SECRET_KEY='+secrets.token_urlsafe(64)+'\nADMIN_PASSWORD='+secrets.token_urlsafe(24)+'\nPOSTGRES_PASSWORD='+secrets.token_urlsafe(24)+'\nNOTIFICATION_WORKER=true\nENVIRONMENT=development\nSMTP_HOST=\nSMTP_FROM=\nTELEGRAM_BOT_TOKEN=\n',encoding='utf-8')
root=Path(__file__).resolve().parents[1]
config={'services':{
 'db':{'image':'pgvector/pgvector:0.8.7-pg17','environment':{'POSTGRES_DB':'workshop','POSTGRES_USER':'workshop','POSTGRES_PASSWORD':'${POSTGRES_PASSWORD}'},'volumes':['test_data:/var/lib/postgresql/data'],'healthcheck':{'test':['CMD-SHELL','pg_isready -U workshop -d workshop'],'interval':'2s','timeout':'5s','retries':20}},
 'api':{'image':args.image,'env_file':'test.env','environment':{'DATABASE_URL':'postgresql+psycopg://workshop:${POSTGRES_PASSWORD}@db:5432/workshop','WEB_DIRECTORY':'/srv/web'},'ports':['127.0.0.1::8000'],'volumes':[str(root/'build/web').replace('\\','/')+':/srv/web:ro'],'depends_on':{'db':{'condition':'service_healthy'}},'restart':'unless-stopped','healthcheck':{'test':['CMD','python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health',timeout=5)"],'interval':'3s','timeout':'5s','retries':20}}
},'volumes':{'test_data':{}}}
(args.directory/'compose.yaml').write_text(json.dumps(config,indent=2),encoding='utf-8')
print('Configuración de prueba preparada; no se reutilizan los datos del taller.')
