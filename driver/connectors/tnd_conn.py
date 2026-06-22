import os
import re
import time
import random
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.support import expected_conditions as ExpCon
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from AI_logic.local_store import girls_to_rise, upsert_record
from AI_logic.misc import translate_rise_msg


# ── Selectors ──────────────────────────────────────────────────
MATCH_BTN_XPATH = '//button[text()="配对"] | //a[contains(@href,"/app/matches")]'
MSG_BTN_XPATH   = '//button[text()="消息"] | //a[contains(@href,"/app/messages")]'
TEXT_AREA_XPATH = '//textarea | //div[@role="textbox"] | //*[@contenteditable="true"]'
BACK_BTN_XPATH  = ('//button[contains(@aria-label,"Back")] | '
                   '//button[contains(@aria-label,"返回")] | '
                   '//a[contains(@href,"/app/recs")]')

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
class TinderConnector:
    def __init__(self, driver):
        self.driver = driver
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.project_dir = os.path.dirname(os.path.dirname(current_dir))
        self.translate_rise_msg_if_needed()

    # ── helpers ──────────────────────────────────────────────

    def _click(self, xpath, timeout=10):
        el = Wait(self.driver, timeout).until(
            ExpCon.element_to_be_clickable((By.XPATH, xpath)))
        el.click()
        return el

    # ── main actions ─────────────────────────────────────────

    def load_main_page(self):
        self.driver.get('https://tinder.com/app/recs')
        print('Waiting for the main page to load')
        try:
            Wait(self.driver, 60).until(
                ExpCon.presence_of_element_located((By.XPATH, MATCH_BTN_XPATH)))
        except TimeoutException:
            print('Timeout — continuing anyway')
        time.sleep(random.uniform(2, 3))
        self._dismiss_gold_popup()

    def _dismiss_gold_popup(self):
        for text in ['以后再说', 'Maybe Later', 'Not now', 'Close', '×', '关闭']:
            try:
                self.driver.find_element(
                    By.XPATH, f'//button[contains(text(),"{text}")] | '
                    f'//*[@aria-label="{text}"] | '
                    f'//span[contains(text(),"{text}")]').click()
                break
            except NoSuchElementException:
                continue

    def close_app(self):
        self.driver.get('about:blank')

    def send_messages(self, messages):
        time.sleep(random.uniform(2, 4))
        text_field = None
        for attempt in range(5):
            for xp in [TEXT_AREA_XPATH, '//textarea',
                       '//div[@role="textbox"]',
                       '//*[@contenteditable="true"]',
                       '//input[@type="text"]',
                       '//form//textarea']:
                try:
                    els = self.driver.find_elements(By.XPATH, xp)
                    if els and els[0].is_displayed():
                        text_field = els[0]
                        break
                except Exception:
                    continue
            if text_field:
                break
            print(f'Waiting for text input... attempt {attempt+1}/5')
            time.sleep(2)

        if not text_field:
            raise Exception('Cannot find message text input')

        for message in messages:
            print(f'Sending: "{message[:60]}..."')
            time.sleep(random.uniform(2, 4))
            text_field.click()
            time.sleep(0.5)
            text_field.send_keys(message)
            time.sleep(random.uniform(2, 4))
            text_field.send_keys(Keys.RETURN)
            time.sleep(random.uniform(1, 2))

        print('Messages sent')
        time.sleep(random.uniform(1, 3))
        try:
            self._click(BACK_BTN_XPATH, timeout=5)
        except (TimeoutException, NoSuchElementException):
            self.driver.get('https://tinder.com/app/recs')
        time.sleep(random.uniform(1, 3))

    # ── conversation navigation ───────────────────────────────

    def _enter_conversation(self, girl_nr=None, tab='auto'):
        """Open a conversation. tab='match' for new matches only,
        tab='msg' for existing conversations, tab='auto' tries both."""
        print(f'Entering conversation (nr={girl_nr}, tab={tab})')
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except Exception:
            pass

        if tab == 'match':
            strategies = [['配对', 'Matches']]
        elif tab == 'msg':
            strategies = [['消息', 'Messages']]
        else:
            strategies = [['配对', 'Matches'], ['消息', 'Messages']]

        for btn_texts in strategies:
            self.driver.get('https://tinder.com/app/recs')
            time.sleep(random.uniform(3, 5))
            for txt in btn_texts:
                try:
                    btns = self.driver.find_elements(
                        By.XPATH, f'//button[text()="{txt}"]')
                    if btns:
                        btns[0].click()
                        time.sleep(random.uniform(2, 3))
                        break
                except Exception:
                    continue
            if self._click_conversation(girl_nr):
                return True

        print('No conversations found')
        return False

    def _click_conversation(self, girl_nr):
        """Find and click a conversation entry on the current page."""
        for tag in ['a', 'button', 'div', 'li']:
            els = self.driver.find_elements(By.TAG_NAME, tag)
            candidates = []
            for el in els:
                try:
                    if not el.is_displayed() or el.size['width'] < 30:
                        continue
                    href = (el.get_attribute('href') or '').lower()
                    if '/messages/' in href:
                        candidates.append(el)
                except Exception:
                    continue
            if candidates:
                idx = min(girl_nr - 1, len(candidates) - 1) if girl_nr else 0
                if idx < 0:
                    break
                el = candidates[idx]
                try:
                    el.click()
                except Exception:
                    self.driver.execute_script('arguments[0].click();', el)
                time.sleep(random.uniform(2, 4))
                return '/messages/' in self.driver.current_url
        return False

    def enter_messages(self, girl_nr=None):
        if not self._enter_conversation(girl_nr, tab='msg'):
            raise Exception('Cannot open any conversation')
        print('Message history entered')

    def open_match_and_get_info(self):
        """Open a NEW match from '配对' tab. Returns (name, bio).
        Reads the profile card BEFORE entering conversation to grab bio text."""
        print('open_match_and_get_info()')
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except Exception:
            pass
        self.driver.get('https://tinder.com/app/recs')
        time.sleep(random.uniform(3, 5))

        # Click '配对' tab
        clicked = False
        for txt in ['配对', 'Matches']:
            try:
                btns = self.driver.find_elements(
                    By.XPATH, f'//button[text()="{txt}"]')
                if btns:
                    btns[0].click()
                    time.sleep(random.uniform(2, 3))
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            return None, ''

        # Click the first match — this opens a profile card (NOT chat yet)
        match_clicked = False
        for selector in ['a[href*="/app/messages/"]', 'div[role="link"]']:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                convs = [e for e in els
                         if e.get_attribute('href')
                         and '/messages/' in (e.get_attribute('href') or '')]
                if convs:
                    convs[0].click()
                    time.sleep(random.uniform(2, 4))
                    match_clicked = True
                    break
            except Exception:
                continue
        if not match_clicked:
            return None, ''

        # Now on the profile card — extract name and bio
        name = self.get_name_age()

        # Try to get bio text from the profile card (before entering chat)
        bio = ''
        try:
            # The profile card might be a dialog or a full page
            body = self.driver.find_element(By.TAG_NAME, 'body').text
            # Try to find the bio section — it's usually between the name and
            # the "基本信息" (Basic Info) section
            lines = body.split('\n')
            name_idx = -1
            for i, line in enumerate(lines):
                if name and name in line:
                    name_idx = i
                    break
            if name_idx >= 0:
                # Bio is typically the text right after the name, before
                # any section headers like "基本信息" / "兴趣" / "距离"
                bio_lines = []
                for line in lines[name_idx + 1:]:
                    if any(kw in line for kw in
                           ['基本信息', '兴趣', '距离', 'km', '公里',
                            'Instagram', 'Spotify', 'Anthem',
                            '举报', '屏蔽', '配对', '消息']):
                        break
                    if line.strip() and line != name:
                        bio_lines.append(line.strip())
                bio = ' '.join(bio_lines)
        except Exception:
            pass

        print(f'open_match_and_get_info → name="{name}" bio="{bio[:100] if bio else "(empty)"}"')
        return name, bio or ''

    def get_msgs(self, girl_nr=None):
        if not self._enter_conversation(girl_nr, tab='msg'):
            raise Exception('Cannot open any conversation')
        messages = []
        for xp in ['//div[@dir="auto"]', '//span[@dir="auto"]',
                   '//div[contains(@class,"msg")]']:
            try:
                found = self.driver.find_elements(By.XPATH, xp)
                if len(found) > 2:
                    messages = found
                    break
            except Exception:
                continue
        if not messages:
            messages = self.driver.find_elements(
                By.CSS_SELECTOR, 'div[dir="auto"], span[dir="auto"]')
        if not messages:
            return ''
        messages = messages[-8:]
        return align_messages(messages)

    def count_new_messages(self):
        """Count unread conversations via the '消息' panel."""
        self.driver.get('https://tinder.com/app/recs')
        time.sleep(random.uniform(3, 5))
        for txt in ['消息', 'Messages']:
            try:
                btns = self.driver.find_elements(
                    By.XPATH, f'//button[text()="{txt}"]')
                if btns:
                    btns[0].click()
                    time.sleep(random.uniform(2, 3))
                    break
            except Exception:
                continue
        count = len(self.driver.find_elements(
            By.CSS_SELECTOR, 'a[href*="/app/messages/"]'))
        print(f'New messages: {count}')
        return count

    def get_name_age(self):
        for xp in ['//h1', '//h1/span', '//header//span',
                   '//div[@role="heading"]']:
            try:
                raw = self.driver.find_element(By.XPATH, xp).text.strip()
                if raw and len(raw) < 80 and 'Tinder' not in raw:
                    m = re.search(r'与\s*(\S+)\s*配对', raw)
                    name = m.group(1) if m else raw
                    return name
            except NoSuchElementException:
                continue
        return self.driver.title.replace('Tinder', '').strip(' |·-')[:30]

    # ── rise ─────────────────────────────────────────────────

    def rise_girls(self):
        try:
            self._click(MSG_BTN_XPATH, timeout=5)
        except TimeoutException:
            pass
        time.sleep(random.uniform(1, 2))
        self.translate_rise_msg_if_needed()
        with open(f'{self.project_dir}/AI_logic/cached_messages/rise_msg.txt',
                  'r', encoding='utf-8') as f:
            rise_msg = f.read()
        to_rise = girls_to_rise()
        for girl_nr in range(11, 20):
            self.enter_messages(girl_nr)
            name_age = self.get_name_age()
            if name_age in to_rise:
                print(f'Rising {name_age}')
                self.send_messages([rise_msg])
                upsert_record(name_age, not_to_rise=True)
                time.sleep(random.uniform(1, 2))
        print('All girls rised')

    def translate_rise_msg_if_needed(self):
        cached = f'{self.project_dir}/AI_logic/cached_messages/rise_msg.txt'
        if not os.path.isfile(cached):
            orig = (f'{self.project_dir}/AI_logic/cached_messages/'
                    'rise_msg_orig.txt')
            with open(orig, 'r', encoding='utf-8') as f:
                orig_msg = f.read()
            translated = translate_rise_msg(orig_msg)
            with open(cached, 'w', encoding='utf-8') as f:
                f.write(translated)


# ── misc ─────────────────────────────────────────────────────

def align_messages(messages):
    """Label messages as 'You:' or 'Girl:' based on the text prefix
    Tinder adds to each message bubble."""
    if not messages:
        return ''
    print(f'[align] {len(messages)} raw elements')

    # Dump parent HTML of first and last message to understand DOM structure
    for idx in [0, -1]:
        try:
            parent = messages[idx].find_element(By.XPATH, '..')
            gp = parent.find_element(By.XPATH, '..')
            print(f'[align] msg[{idx}] parent tag=<{parent.tag_name}> '
                  f'class="{parent.get_attribute("class") or ""}" '
                  f'style="{parent.get_attribute("style") or ""}"')
            print(f'[align] msg[{idx}] grandparent tag=<{gp.tag_name}> '
                  f'class="{gp.get_attribute("class") or ""}" '
                  f'style="{gp.get_attribute("style") or ""}"')
        except Exception as e:
            print(f'[align] msg[{idx}] dump error: {e}')

    results = []
    seen = set()
    for msg in messages:
        try:
            raw = msg.text.strip()
            # Skip timestamps and status messages
            if not raw:
                continue
            if any(kw in raw for kw in ('发送', 'Sent', '已读', 'Read', '已发送')):
                continue
            # Deduplicate (Tinder shows each message twice in DOM)
            key = raw[:60]
            if key in seen:
                continue
            seen.add(key)

            # Tinder prepends "你:" or "You:" on OUR message bubbles
            # Remove the prefix and label accordingly
            if raw.startswith('你:'):
                content = raw[2:].strip()
                results.append(('You', content))
            elif raw.startswith('You:'):
                content = raw[4:].strip()
                results.append(('You', content))
            else:
                results.append(('Girl', raw))
        except Exception:
            continue

    text = ''
    for label, content in results:
        text += f'{label}: {content}\n'
    print(f'[align] → {len(results)} messages: '
          f'You={sum(1 for l,_ in results if l=="You")} '
          f'Girl={sum(1 for l,_ in results if l=="Girl")}')
    return text
