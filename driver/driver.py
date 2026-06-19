from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from os import path, makedirs, listdir, remove
import sys


LOCK_FILE = 'parent.lock'


def start_driver(head):
    print('Starting driver')
    options = Options()
    if not head:
        options.add_argument('--headless')

    script_path = path.dirname(path.abspath(__file__))
    profile_dir = path.join(script_path, 'FirefoxProfile')
    makedirs(profile_dir, exist_ok=True)

    # Remove stale lock file (left by a previous crashed Firefox session).
    # If Firefox is currently running with this profile the file cannot be
    # removed — in that case we print a clear message and exit.
    lock_path = path.join(profile_dir, LOCK_FILE)
    if path.isfile(lock_path):
        try:
            remove(lock_path)
            print('Removed stale Firefox profile lock.')
        except PermissionError:
            print('=' * 60)
            print('ERROR: Firefox profile is locked.')
            print('This means Firefox is currently running with the')
            print('TinderGPT profile. Close ALL Firefox windows first,')
            print('then re-run TinderGPT.')
            print('=' * 60)
            sys.exit(1)

    profile_contents = [
        f for f in listdir(profile_dir)
        if f not in ('.gitignore',)
    ]
    if profile_contents:
        print(f'Using Firefox profile: {profile_dir}')
        options.add_argument('-profile')
        options.add_argument(profile_dir)
    else:
        print('FirefoxProfile is empty — using a temporary profile.'
              ' Run the setup step to persist your Tinder login.')

    # ── Hide automation flags ────────────────────────────
    options.set_preference('dom.webdriver.enabled', False)
    options.set_preference('useAutomationExtension', False)
    options.set_preference('dom.webdriver.enabled', False)
    # Prevent "browser is being controlled by automation" banner
    options.set_preference('browser.privatebrowsing.autostart', False)

    driver = webdriver.Firefox(options=options)

    # Mask navigator.webdriver property
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.maximize_window()
    print('Driver activated')

    return driver
