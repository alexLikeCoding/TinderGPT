"""
Auto-respond loop — polls for new messages every few minutes.
Run this alongside main.py to never miss a reply.

Usage:  python auto_respond.py
"""
import time
import random
import requests

BASE = 'http://localhost:8080'
INTERVAL = 120  # seconds (2 min)

print('Auto-respond started (Ctrl+C to stop)')
print(f'Polling every {INTERVAL}s\n')

while True:
    try:
        r = requests.get(f'{BASE}/respond_all', timeout=120)
        if r.status_code == 200:
            print(f'[{time.strftime("%H:%M:%S")}] check complete')
        else:
            print(f'[{time.strftime("%H:%M:%S")}] '
                  f'respond_all returned {r.status_code}')
    except requests.ConnectionError:
        print('[warn] Cannot connect to main.py — is it running?')
    except Exception as e:
        print(f'[error] {e}')

    time.sleep(INTERVAL + random.randint(-10, 10))
