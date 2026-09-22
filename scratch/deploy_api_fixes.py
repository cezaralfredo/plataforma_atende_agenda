import urllib.request
import ssl
import json
import base64

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

PORTAINER_URL = 'https://portainer.anauedesign.com.br/api'
PORTAINER_TOKEN = 'ptr_00oATuCFJd+LlLWoQ+c0PNSSt3G1lQsjh5/p5h9oW6g='
ENDPOINT_ID = 3

def exec_cmd(container_id, cmd, user="root"):
    payload = json.dumps({'AttachStdout': True, 'AttachStderr': True, 'User': user, 'Cmd': cmd}).encode()
    req_exec = urllib.request.Request(f'{PORTAINER_URL}/endpoints/{ENDPOINT_ID}/docker/containers/{container_id}/exec', data=payload, headers={'X-API-Key': PORTAINER_TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req_exec, context=ctx, timeout=15) as resp:
        exec_id = json.loads(resp.read().decode())['Id']

    start_req = urllib.request.Request(f'{PORTAINER_URL}/endpoints/{ENDPOINT_ID}/docker/exec/{exec_id}/start', data=json.dumps({'Detach': False, 'Tty': False}).encode(), headers={'X-API-Key': PORTAINER_TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(start_req, context=ctx, timeout=30) as resp:
        raw = resp.read()
        out = ''
        idx = 0
        while idx < len(raw):
            if idx + 8 > len(raw):
                out += raw[idx:].decode('utf-8', errors='replace')
                break
            size = int.from_bytes(raw[idx+4:idx+8], byteorder='big')
            idx += 8
            out += raw[idx:idx+size].decode('utf-8', errors='replace')
            idx += size
        return out

def write_container_file(container_id, target_path, local_content):
    b64 = base64.b64encode(local_content.encode('utf-8')).decode('ascii')
    cmd = ['python3', '-c', f'''
import base64
with open("{target_path}", "w", encoding="utf-8") as f:
    f.write(base64.b64decode("{b64}").decode("utf-8"))
print("Wrote {target_path}")
''']
    return exec_cmd(container_id, cmd, user="root")

url = PORTAINER_URL + f'/endpoints/{ENDPOINT_ID}/docker/containers/json'
req = urllib.request.Request(url, headers={'X-API-Key': PORTAINER_TOKEN})
with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
    containers = json.loads(resp.read().decode())

api_id = [c['Id'] for c in containers if 'api' in str(c.get('Names', [])).lower()][0]
hermes_id = [c['Id'] for c in containers if 'hermes' in str(c.get('Names', [])).lower()][0]

print("API container:", api_id[:12])

with open("e:/Projetos/plataforma_atende_agenda/app/mcp/tools.py", "r", encoding="utf-8") as f:
    tools_code = f.read()
print(write_container_file(api_id, "/app/app/mcp/tools.py", tools_code))

with open("e:/Projetos/plataforma_atende_agenda/app/services/user_service.py", "r", encoding="utf-8") as f:
    user_svc_code = f.read()
print(write_container_file(api_id, "/app/app/services/user_service.py", user_svc_code))

with open("e:/Projetos/plataforma_atende_agenda/app/services/asaas_client.py", "r", encoding="utf-8") as f:
    asaas_code = f.read()
print(write_container_file(api_id, "/app/app/services/asaas_client.py", asaas_code))

print("Restarting API container...")
restart_req = urllib.request.Request(f'{PORTAINER_URL}/endpoints/{ENDPOINT_ID}/docker/containers/{api_id}/restart', data=b'', headers={'X-API-Key': PORTAINER_TOKEN})
urllib.request.urlopen(restart_req, context=ctx, timeout=30)
print("API container restarted!")

# Let's test the exact call in API container!
test_code = '''
import asyncio
from app.database import SessionLocal
from app.mcp.tools import handle_tool_call

db = SessionLocal()
args = {
    "client_name": "Cezar Alfredo",
    "phone": "558596277707",
    "professional_id": "5",
    "service_id": "3",
    "start_time": "2026-09-23T17:00:00-03:00",
    "end_time": "2026-09-23T17:45:00-03:00",
    "cpf_cnpj": "38801027320"
}

async def run():
    res = await handle_tool_call("solicitar_agendamento_orquestrador_n8n", args, db)
    print("TEST RESULT:", res)

asyncio.run(run())
db.close()
'''

print("Executing test on API container...")
output = exec_cmd(api_id, ['python', '-c', test_code], user="root")
print(output)
