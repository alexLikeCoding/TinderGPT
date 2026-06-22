"""
Auto-respond loop — replies to messages + sends openers to new matches.
Run this alongside main.py.

Usage:  python auto_respond.py
"""
import warnings
warnings.filterwarnings('ignore')

import time
import random
import requests

BASE = 'http://localhost:8080'
INTERVAL = 120  # seconds between cycles (2 min)
MAX_OPENERS = 3  # max openers per cycle

print('Auto-respond + auto-opener started (Ctrl+C to stop)')
print(f'Polling every {INTERVAL}s\n')

while True:
    timestamp = time.strftime('%H:%M:%S')

    # 1. Reply to all unread messages
    try:
        r = requests.get(f'{BASE}/respond_all', timeout=180)
        if r.status_code == 200:
            print(f'[{timestamp}] replies: done')
        else:
            print(f'[{timestamp}] replies: HTTP {r.status_code}')
    except requests.ConnectionError:
        print(f'[{timestamp}] WARN: cannot connect - is main.py running?')
    except requests.ReadTimeout:
        print(f'[{timestamp}] replies: timeout (main.py may be busy)')
    except Exception as e:
        print(f'[{timestamp}] replies error: {e}')
        continue
    except Exception as e:
        print(f'[{timestamp}] replies error: {e}')

    # Small pause between reply and opener (let the browser settle)
    time.sleep(random.uniform(2, 4))

    # 2. Send openers to new matches
    for i in range(MAX_OPENERS):
        try:
            r = requests.get(f'{BASE}/opener', timeout=180)
            data = r.json() if r.text else {}
            if 'error' in data:
                if i == 0:
                    print(f'[{timestamp}] openers: no new matches')
                break
            if data.get('status') == 'skipped':
                print(f'[{timestamp}] opener {i+1}: {data.get("name", "?")} already messaged, skip')
                continue
            print(f'[{timestamp}] opener {i+1}: sent to {data.get("name", "?")}')
        except requests.ConnectionError:
            print(f'[{timestamp}] opener {i+1}: connection refused')
            break
        except requests.ReadTimeout:
            print(f'[{timestamp}] opener {i+1}: timeout')
        except Exception as e:
            print(f'[{timestamp}] opener {i+1}: {e}')
            break
        time.sleep(random.uniform(5, 10))

    time.sleep(INTERVAL + random.randint(-10, 10))
