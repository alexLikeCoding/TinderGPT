"""
Deep diagnostic — dumps all clickable elements and page structure.
"""
from driver.driver import start_driver
from selenium.webdriver.common.by import By
import time

driver = start_driver(head=True)
driver.get("https://tinder.com")
print("Waiting 15s... Make sure you're LOGGED IN on the Firefox window!")
time.sleep(15)

print(f"\nPage title: {driver.title}")
print(f"Current URL: {driver.current_url}")

# Check if on login page
if 'login' in driver.current_url.lower() or 'auth' in driver.current_url.lower():
    print("\n*** You are NOT logged in! Please log in to Tinder first. ***")
    print("Press Enter in the terminal after you've logged in...")
    input()
    time.sleep(3)

print("\n=== ALL LINKS (a tags) ===")
links = driver.find_elements(By.TAG_NAME, 'a')
for a in links[:30]:
    href = a.get_attribute('href') or ''
    text = (a.text or '')[:50]
    aria = a.get_attribute('aria-label') or ''
    if href or aria:
        print(f"  text='{text}' href='{href[:80]}' aria='{aria}'")

print("\n=== ALL BUTTONS ===")
buttons = driver.find_elements(By.TAG_NAME, 'button')
for b in buttons[:20]:
    text = (b.text or '')[:50]
    aria = b.get_attribute('aria-label') or ''
    print(f"  text='{text}' aria='{aria}'")

print("\n=== NAV elements ===")
navs = driver.find_elements(By.TAG_NAME, 'nav')
for i, n in enumerate(navs):
    print(f"  nav[{i}]: {n.get_attribute('outerHTML')[:200]}")

print("\n=== TEXT INPUTS & TEXTAREAS ===")
for tag in ['textarea', 'input']:
    els = driver.find_elements(By.TAG_NAME, tag)
    for el in els:
        t = el.get_attribute('type') or ''
        p = el.get_attribute('placeholder') or ''
        name = el.get_attribute('name') or ''
        if t or p:
            print(f"  <{tag}> type='{t}' placeholder='{p}' name='{name}'")

print("\n=== Elements with 'role' attribute ===")
for role_val in ['navigation', 'button', 'link', 'textbox', 'main', 'tab']:
    try:
        els = driver.find_elements(By.CSS_SELECTOR, f'[role="{role_val}"]')
        if els:
            print(f"  role='{role_val}': {len(els)} elements")
    except:
        pass

print("\nDone!")
driver.quit()
