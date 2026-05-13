import requests
base = 'http://0.0.0.0:8000'
for path in ['/api/greenhouses', '/api/greenhouses?active_only=true']:
    try:
        r = requests.get(base + path, timeout=10)
        print(f'{path} {r.status_code}')
        print((r.text or '')[:100])
    except Exception as e:
        print(f'{path} ERR {str(e)}')
