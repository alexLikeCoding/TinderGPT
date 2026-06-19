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

# URL patterns that are NOT conversation pages
_NOT_CONVERSATION = {'likes-you', 'profile', 'explore', 'recs#',
                     'recs?', 'help.tinder', 'go.tinder', 'login'}


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

    def _enter_conversation(self, girl_nr=None):
        """Open a conversation. Two strategies: '匹配' tab or '消息' panel."""
        print(f'Entering conversation (nr={girl_nr})')
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except Exception:
            pass

        for btn_texts in [['配对', 'Matches'], ['消息', 'Messages']]:
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
        if not self._enter_conversation(girl_nr):
            raise Exception('Cannot open any conversation')
        print('Message history entered')

    def open_messages_and_get_name(self):
        if not self._enter_conversation(girl_nr=None):
            return None
        return self.get_name_age()

    def get_msgs(self, girl_nr=None):
        if not self._enter_conversation(girl_nr):
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
        messages = messages[-8:]
        return align_messages(messages)

    def count_new_messages(self):
        self.driver.get('https://tinder.com/app/messages')
        time.sleep(random.uniform(2, 3))
        return len(self.driver.find_elements(
            By.CSS_SELECTOR, 'a[href*="/app/messages/"]'))

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
    your_color = 'rgb(255, 255, 255)'
    her_color = 'rgb(33, 38, 46)'
    text = ''
    for msg in messages:
        try:
            color = msg.value_of_css_property('color')
        except Exception:
            continue
        if color == your_color:
            text += 'You: ' + msg.text + '\n'
        elif color == her_color:
            text += 'Girl: ' + msg.text + '\n'
    return text
