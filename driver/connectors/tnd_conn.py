from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.support import expected_conditions as ExpCon
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from AI_logic.local_store import girls_to_rise, upsert_record
from AI_logic.misc import translate_rise_msg
import time
import random
import os
import sys


# ── Resilient selectors (text-based, survives Tinder UI updates) ──
# Navigation
MATCH_BTN_XPATH = '//button[text()="配对"] | //a[contains(@href,"/app/matches")] | //*[@aria-label="Matches"]'
MSG_BTN_XPATH = '//button[text()="消息"] | //a[contains(@href,"/app/messages")] | //*[@aria-label="Messages"]'
PROFILE_LINK_XPATH = '//a[contains(@href,"/app/profile")]'

# Match list
NOT_OPENED_GIRLS_CSS = 'a[href*="/app/messages/"]'

# Conversation view
TEXT_AREA_XPATH = '//textarea | //div[@role="textbox"] | //*[@contenteditable="true"]'
BACK_BTN_XPATH = '//button[contains(@aria-label,"Back")] | //button[contains(@aria-label,"返回")] | //a[contains(@href,"/app/recs")]'
NAME_XPATH = '//h1 | //div[contains(@class,"Name")] | //span[@itemprop="name"]'

# Bio on unwritten-girl profile card
BIO_SHORT_XPATH = '//div[@role="tabpanel"]//div[contains(text(),"关于")]/following-sibling::div'
BIO_FULL_XPATH = '//div[@role="tabpanel"]'


class TinderConnector():
    def __init__(self, driver):
        self.driver = driver
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.project_dir = os.path.dirname(os.path.dirname(current_dir))
        self.translate_rise_msg_if_needed()

    # ── helpers ──────────────────────────────────────────────

    def _click(self, xpath, timeout=10):
        """Wait for an element to be clickable, then click it."""
        el = Wait(self.driver, timeout).until(
            ExpCon.element_to_be_clickable((By.XPATH, xpath)))
        el.click()
        return el

    def _find(self, xpath):
        return self.driver.find_element(By.XPATH, xpath)

    def _finds(self, xpath):
        return self.driver.find_elements(By.XPATH, xpath)

    def _wait_for(self, xpath, timeout=30):
        return Wait(self.driver, timeout).until(
            ExpCon.presence_of_element_located((By.XPATH, xpath)))

    # ── main actions ─────────────────────────────────────────

    def load_main_page(self):
        self.driver.get("https://tinder.com/app/recs")
        print('Waiting for the main page to load')
        try:
            # Wait for nav to appear (indicates page is ready)
            Wait(self.driver, 60).until(
                ExpCon.presence_of_element_located((By.XPATH, MATCH_BTN_XPATH)))
        except TimeoutException:
            print('Timeout waiting for main page — trying to continue anyway')
        time.sleep(random.uniform(2, 3))
        # Close Tinder Gold popup if present
        self._dismiss_gold_popup()

    def _dismiss_gold_popup(self):
        for text in ['以后再说', 'Maybe Later', 'Not now', 'Close', '×', '关闭']:
            try:
                btn = self.driver.find_element(
                    By.XPATH,
                    f'//button[contains(text(),"{text}")] | '
                    f'//*[@aria-label="{text}"] | '
                    f'//span[contains(text(),"{text}")]'
                )
                btn.click()
                print(f'Dismissed popup: {text}')
                break
            except NoSuchElementException:
                continue

    def close_app(self):
        print('Closing Tinder')
        self.driver.get("about:blank")

    def send_messages(self, messages):
        # Debug: show what page we're on
        print(f'[send_messages] Current URL: {self.driver.current_url}')
        screenshot_path = os.path.join(self.project_dir, 'debug_send_msg.png')
        self.driver.save_screenshot(screenshot_path)
        print(f'[send_messages] Screenshot saved to {screenshot_path}')

        # Dump all visible text to understand what page we're on
        body_text = self.driver.find_element(By.TAG_NAME, 'body').text[:300]
        print(f'[send_messages] Page body preview: {body_text}')

        # Wait for the conversation to fully load
        time.sleep(random.uniform(2, 4))
        text_field = None
        for attempt in range(5):
            for xp in [
                TEXT_AREA_XPATH,
                '//textarea',
                '//div[@role="textbox"]',
                '//*[@contenteditable="true"]',
                '//input[@type="text"]',
                '//div[contains(@class,"message")]//textarea',
                '//form//textarea',
            ]:
                try:
                    els = self.driver.find_elements(By.XPATH, xp)
                    if els and els[0].is_displayed():
                        text_field = els[0]
                        print(f'Found text input: {xp}')
                        break
                except Exception:
                    continue
            if text_field:
                break
            print(f'Waiting for text input... attempt {attempt+1}/5')
            time.sleep(2)

        if not text_field:
            raise Exception('Cannot find message text input on page')

        for i, message in enumerate(messages):
            print(f'Sending msg {i+1}/{len(messages)}: "{message[:50]}..."')
            time.sleep(random.uniform(2, 4))
            text_field.click()
            time.sleep(0.5)
            text_field.send_keys(message)
            time.sleep(random.uniform(2, 4))
            text_field.send_keys(Keys.RETURN)
            time.sleep(random.uniform(1, 2))

        print(f'{len(messages)} messages sent successfully')
        time.sleep(random.uniform(1, 3))
        # Return to recs page
        try:
            self._click(BACK_BTN_XPATH, timeout=5)
        except (TimeoutException, NoSuchElementException):
            self.driver.get('https://tinder.com/app/recs')
        time.sleep(random.uniform(1, 3))
        time.sleep(random.uniform(1, 3))
        # Return to main / recs page
        try:
            self._click(BACK_BTN_XPATH, timeout=5)
        except (TimeoutException, NoSuchElementException):
            self.driver.get("https://tinder.com/app/recs")
        time.sleep(random.uniform(1, 3))

    # ── messages ─────────────────────────────────────────────

    def enter_messages(self, girl_nr=None):
        print('Entering messages tab')
        self._click(MSG_BTN_XPATH)
        time.sleep(random.uniform(2, 3))

        if girl_nr:
            # Click nth conversation in the message list
            try:
                convs = self.driver.find_elements(
                    By.CSS_SELECTOR, NOT_OPENED_GIRLS_CSS)
                if len(convs) >= girl_nr:
                    convs[girl_nr - 1].click()
                else:
                    print(f'Only {len(convs)} conversations, '
                          f'cannot open nr {girl_nr}')
            except Exception:
                print('Could not find conversation list')
        else:
            # Open first unread / most recent conversation
            try:
                convs = self.driver.find_elements(
                    By.CSS_SELECTOR, NOT_OPENED_GIRLS_CSS)
                if convs:
                    convs[0].click()
                else:
                    print('No conversations found')
            except Exception:
                print('Could not open conversation')

        time.sleep(random.uniform(2, 4))
        print('Message history entered')

    def get_msgs(self, girl_nr=None):
        self.enter_messages(girl_nr)
        # Collect visible message bubbles
        messages = self.driver.find_elements(
            By.CSS_SELECTOR, '[class*="message"], [class*="Message"], '
            'div[dir="auto"], span[class*="text"]')
        if not messages:
            # fallback: try common chat bubble patterns
            messages = self.driver.find_elements(
                By.XPATH, '//div[contains(@class,"msg")] | //div[@dir="auto"]')
        print(f'Found {len(messages)} message elements')
        messages = messages[-8:]  # last 8
        return align_messages(messages)

    def count_new_messages(self):
        try:
            self._click(MSG_BTN_XPATH, timeout=5)
        except TimeoutException:
            pass
        time.sleep(random.uniform(1, 2))
        # Count conversation links (each is a match)
        convs = self.driver.find_elements(By.CSS_SELECTOR, NOT_OPENED_GIRLS_CSS)
        return len(convs)

    def get_name_age(self):
        try:
            name_age = self._find(NAME_XPATH).text
        except NoSuchElementException:
            name_age = self.driver.title
        print(f'Got name_age: {name_age}')
        return name_age

    # ── openers / matches ────────────────────────────────────

    def count_not_opened_girls(self):
        try:
            self._click(MATCH_BTN_XPATH, timeout=5)
        except TimeoutException:
            pass
        time.sleep(random.uniform(2, 4))
        icons = self._finds("//div[@role='img']")
        return max(0, len(icons) - 2)

    def open_messages_and_get_name(self):
        """Try multiple strategies to open a conversation and return the
        match's name. Returns name on success, None if no conversations."""
        print('open_messages_and_get_name()')

        strategies = [
            # Strategy A: recs → click "配对"(matches tab) → click girl avatar
            lambda: self._try_recs_to_match_chat(),
            # Strategy B: directly go to /app/messages
            lambda: self._try_messages_url(),
        ]

        for i, strat in enumerate(strategies):
            try:
                result = strat()
                if result:
                    print(f'Strategy {chr(65+i)} succeeded → name="{result}"')
                    return result
            except Exception as e:
                print(f'Strategy {chr(65+i)} failed: {e}')

        print('All strategies failed — no conversations found')
        return None

    def _try_recs_to_match_chat(self):
        """Go to recs, click '配对' tab, click first match avatar."""
        self.driver.get('https://tinder.com/app/recs')
        time.sleep(random.uniform(3, 5))

        # Click "配对" button to see match list
        for btn_text in ['配对', 'Matches']:
            try:
                btns = self.driver.find_elements(
                    By.XPATH, f'//button[text()="{btn_text}"]')
                if btns:
                    btns[0].click()
                    time.sleep(random.uniform(2, 3))
                    break
            except Exception:
                continue

        return self._click_first_conversation()

    def _try_messages_url(self):
        """Go directly to /app/messages."""
        self.driver.get('https://tinder.com/app/messages')
        time.sleep(random.uniform(3, 5))
        return self._click_first_conversation()

    def _click_first_conversation(self):
        """On the current page, find and click the first conversation link."""
        for selector in [
            'a[href*="/app/messages/"]',
            'a[href*="messages"]',
            'div[role="link"]',
            'li a',
        ]:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                convs = [e for e in els
                         if e.get_attribute('href')
                         and '/messages/' in (e.get_attribute('href') or '')]
                if convs:
                    convs[0].click()
                    time.sleep(random.uniform(2, 4))
                    return self._get_name_from_header()
            except Exception:
                continue
        return None

    def _get_name_from_header(self):
        """Extract match name from the open conversation."""
        for xp in ['//h1', '//h1/span', '//header//span',
                   '//div[@role="heading"]', '//span[contains(@class,"name")]']:
            try:
                name = self.driver.find_element(By.XPATH, xp).text.strip()
                if name and len(name) < 50:
                    return name
            except NoSuchElementException:
                continue
        return self.driver.title.replace('Tinder', '').strip(' |·-')[:30] or None

    def _try_get_bio_via_match_tab(self, girl_nr):
        """Click '配对' button, find new-match cards, open one, return (name, bio)."""
        try:
            # Click the Matches nav button (text="配对")
            btns = self.driver.find_elements(By.XPATH, '//button[text()="配对"]')
            if btns:
                btns[0].click()
                time.sleep(random.uniform(2, 3))
        except Exception:
            return None, None

        return self._click_match_card_and_extract(girl_nr)

    def _try_get_bio_via_messages(self, girl_nr):
        """Look through message list for unmessaged matches."""
        try:
            self._click(MSG_BTN_XPATH, timeout=5)
            time.sleep(random.uniform(2, 3))
        except Exception:
            return None, None

        return self._click_match_card_and_extract(girl_nr)

    def _click_match_card_and_extract(self, girl_nr):
        """On the current page, find a match card, click it, extract name+bio."""
        # Try to find clickable elements that look like match cards
        # Look for <a> links to profiles or divs that are clickable
        for selector in [
            'a[href*="/app/messages/"]',               # conversation links
            'a[href*="/profile"]',                       # profile links
            'div[class*="match"] a',                     # match cards with links
            'div[role="button"]',                         # generic clickable
            'div[class*="Preview"]',                      # preview cards
            'div[style*="background-image"]',             # photo cards
        ]:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                # Filter to real cards (skip nav icons etc)
                cards = [c for c in cards if c.size['width'] > 50]
                if len(cards) >= girl_nr:
                    print(f'Found {len(cards)} cards via "{selector}"')
                    cards[girl_nr - 1].click()
                    time.sleep(3)
                    return self._extract_name_and_bio()
            except Exception:
                continue

        return None, None

    # UI garbage phrases to filter out of bio extraction
    _UI_NOISE = {'配对', '消息', 'BOOST', '工作模式', '安全工具包',
                 '不', 'SUPER LIKE', '赞', '初印象', '隐藏', '键盘快捷键',
                 '探索', '跳到主要内容', 'Matches', 'Messages', 'Likes You',
                 'Match', 'Chat', 'No Thanks', 'Maybe Later', 'Get Tinder Gold',
                 'km', '公里', '岁', '距离', '偏好', '筛选', '取消', '应用',
                 '通知', '设置', '帮助', '退出', '删除', '举报', '屏蔽',
                 '资料', '编辑', '预览', '分享', '关注', '粉丝',
                 'Instagram', 'Spotify', 'Anthem', '照片', '验证',
                 '最近活跃', '在线', '距离你', '居住', '工作', '学历',
                 '饮酒', '吸烟', '宠物', '星座', '身高', '体型',
                 '恋爱取向', '性别', '语言', '疫苗接种', 'COVID',
                 '订阅', '管理', '会员', '高级', '付费', 'Tinder Gold',
                 'Tinder Plus', 'Tinder Platinum', '升级', '试用',
                 '折扣', '促销', '套餐', 'Super Like', 'Boost',
                 'Rewind', 'Passport', 'Top Picks', '热门',
                 '活跃', '在线', '已读', '未读', '输入中'}

    def _extract_name_and_bio(self):
        """After opening a profile card, pull out name and bio text."""
        name = None
        bio = ''

        # Try to find name (<h1>)
        for name_xp in ['//h1', '//h1/span']:
            try:
                name = self.driver.find_element(By.XPATH, name_xp).text.strip()
                if name and name not in self._UI_NOISE:
                    break
            except NoSuchElementException:
                continue

        if not name:
            # fallback: use page title minus "Tinder" etc
            t = (self.driver.title or '').replace('Tinder', '').strip(' |·-')
            name = t[:40] or 'match'

        # Try to find bio — look for text in the profile dialog that's
        # clearly the girl's description, NOT UI labels
        try:
            # The profile panel shows sections like "关于" (About) with bio below
            dialog = self.driver.find_element(By.XPATH, '//div[@role="dialog"]')
            all_text = dialog.text
        except NoSuchElementException:
            all_text = self.driver.find_element(By.TAG_NAME, 'body').text

        # Split into lines, keep lines that look like real bio content
        lines = all_text.split('\n')
        good_lines = []
        for line in lines:
            line = line.strip()
            # Skip lines that are obviously UI elements
            if not line or len(line) < 3:
                continue
            if line == name:
                continue
            # Check if the line is an exact noise match OR contains
            # Tinder UI terms that would never appear in a real bio
            is_noise = False
            for noise_term in self._UI_NOISE:
                if noise_term in line:
                    is_noise = True
                    break
            if is_noise:
                continue
            good_lines.append(line)

        # Join non-UI lines as the bio
        bio = ' '.join(good_lines)
        # Final safety check: if the bio still looks like UI text
        # (short, full of settings terms), treat it as empty
        noise_count = sum(1 for term in self._UI_NOISE if term in bio)
        if noise_count > 3 or len(bio) < 10:
            bio = ''
        if len(bio) > 500:
            bio = bio[:500]

        print(f'_extract: name="{name}" bio="{bio[:100]}..."')
        return name, bio or ''

    # ── rise ─────────────────────────────────────────────────

    def rise_girls(self):
        try:
            self._click(MSG_BTN_XPATH, timeout=5)
        except TimeoutException:
            pass
        time.sleep(random.uniform(1, 2))

        self.translate_rise_msg_if_needed()
        with open(f'{self.project_dir}/AI_logic/cached_messages/rise_msg.txt',
                  'r', encoding='utf-8') as file:
            rise_msg = file.read()

        to_rise = girls_to_rise()
        for girl_nr in range(11, 20):
            print(f'Trying rise for position {girl_nr}')
            self.enter_messages(girl_nr)
            name_age = self.get_name_age()
            if name_age in to_rise:
                print(f'Rising {name_age}')
                self.send_messages([rise_msg])
                upsert_record(name_age, not_to_rise=True)
                time.sleep(random.uniform(1, 2))
        print("All girls rised")

    def translate_rise_msg_if_needed(self):
        cached = f'{self.project_dir}/AI_logic/cached_messages/rise_msg.txt'
        if not os.path.isfile(cached):
            orig = (f'{self.project_dir}/AI_logic/cached_messages/'
                    'rise_msg_orig.txt')
            with open(orig, 'r', encoding='utf-8') as file:
                orig_rise_msg = file.read()
            rise_msg = translate_rise_msg(orig_rise_msg)
            with open(cached, 'w', encoding='utf-8') as file:
                file.write(rise_msg)


# ── misc ─────────────────────────────────────────────────────

def align_messages(messages):
    your_color = 'rgb(255, 255, 255)'
    her_color = 'rgb(33, 38, 46)'
    message_prompt = ''
    for message in messages:
        try:
            color = message.value_of_css_property('color')
        except Exception:
            continue
        if color == your_color:
            message_prompt += 'You: ' + message.text + '\n'
        elif color == her_color:
            message_prompt += 'Girl: ' + message.text + '\n'
    return message_prompt
