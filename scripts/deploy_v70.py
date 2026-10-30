#!/usr/bin/env python3
"""v7.0 SUPER: Trigger a new Render deploy and verify health."""
import json, time, urllib.request, urllib.error, subprocess

RENDER_API = 'rnd_0d8ubDKRLBAK60JzhsHYQDzepdlK'
SERVICE_ID = 'srv-d88b7h3tqb8s738988cg'

print('🚀 Triggering Render deploy (v7.0 SUPER)...')
HEAD = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd='/home/z/my-project').decode().strip()
print(f'   Using commitId: {HEAD}')
url = f'https://api.render.com/v1/services/{SERVICE_ID}/deploys'
data = json.dumps({"clearCache": "do_not_clear", "commitId": HEAD}).encode()
req = urllib.request.Request(
    url, data=data, method='POST',
    headers={
        'Authorization': f'Bearer {RENDER_API}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
        print(f'✅ Deploy triggered: id={body.get("id")}, status={body.get("status")}')
        deploy_id = body.get('id')
except urllib.error.HTTPError as e:
    print(f'❌ HTTP {e.code}: {e.read().decode()[:300]}')
    deploy_id = None
except Exception as e:
    print(f'❌ Error: {e}')
    deploy_id = None

if not deploy_id:
    raise SystemExit(1)

print(f'\n⏳ Waiting for deploy {deploy_id} (max 5 minutes)...')
url_status = f'https://api.render.com/v1/services/{SERVICE_ID}/deploys/{deploy_id}'
deadline = time.time() + 300
last_status = None
while time.time() < deadline:
    try:
        req = urllib.request.Request(
            url_status, method='GET',
            headers={'Authorization': f'Bearer {RENDER_API}', 'Accept': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            status = body.get('status')
            if status != last_status:
                print(f'  [{time.strftime("%H:%M:%S")}] status={status}')
                last_status = status
            if status in ('live', 'canceled', 'deactivated'):
                break
    except Exception as e:
        print(f'  poll error: {e}')
    time.sleep(10)

print('\n🏥 Verifying https://super-poster-bot.onrender.com/health...')
for i in range(15):
    try:
        req = urllib.request.Request('https://super-poster-bot.onrender.com/health',
                                     headers={'User-Agent': 'v70-super-check/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f'✅ /health → {resp.status}')
            print('🎉 v7.0 SUPER deployment is LIVE.')
            raise SystemExit(0)
    except Exception as e:
        print(f'  attempt {i+1} failed: {e}')
        time.sleep(15)
print('❌ Health check failed after 15 attempts')
raise SystemExit(1)
