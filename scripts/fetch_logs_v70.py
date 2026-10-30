#!/usr/bin/env python3
"""Fetch Render logs to diagnose message-add issue."""
import urllib.request, json

RENDER_API = 'rnd_0d8ubDKRLBAK60JzhsHYQDzepdlK'
SERVICE_ID = 'srv-d88b7h3tqb8s738988cg'
OWNER_ID = 'tea-d5vm2e2qcgvc739p63t0'

# Try multiple log endpoints
endpoints = [
    f'https://api.render.com/v1/services/{SERVICE_ID}/deploys?limit=3',
]

for url in endpoints:
    print(f'\n━━━ {url} ━━━')
    try:
        req = urllib.request.Request(
            url, method='GET',
            headers={
                'Authorization': f'Bearer {RENDER_API}',
                'Accept': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            # فقط آخر 3 deploys
            if isinstance(body, list):
                for d in body[:3]:
                    print(f"deploy {d.get('id')}: status={d.get('status')}, commit={d.get('commitId', '?')[:8]}, createdAt={d.get('createdAt')}")
            else:
                print(json.dumps(body, indent=2)[:500])
    except Exception as e:
        print(f'Error: {e}')

# Try to fetch logs via different endpoints
print('\n━━━ Try /logs endpoint variants ━━━')
log_endpoints = [
    f'https://api.render.com/v1/services/{SERVICE_ID}/logs?limit=100',
    f'https://api.render.com/v1/services/{SERVICE_ID}/deploys/dep-dbh4nlkipgvc73dp8530/logs?limit=100',
]
for url in log_endpoints:
    print(f'\nTrying: {url}')
    try:
        req = urllib.request.Request(
            url, method='GET',
            headers={
                'Authorization': f'Bearer {RENDER_API}',
                'Accept': 'application/x-ndjson',
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            print(body[:2000])
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {e.read().decode()[:300]}')
    except Exception as e:
        print(f'Error: {e}')
