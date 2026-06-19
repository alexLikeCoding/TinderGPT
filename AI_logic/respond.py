import json
import os
import re
import traceback
import requests
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnableLambda
from AI_logic.rule_base.rules_db_conn import query_rule
from AI_logic.local_store import get_record, upsert_record
from AI_logic.config import create_llm
from dotenv import load_dotenv, find_dotenv
from pushbullet import Pushbullet
from tenacity import retry, stop_after_attempt, wait_fixed


def _get_text(llm_output):
    """Extract plain text from LLM response, handling various formats."""
    if hasattr(llm_output, 'content'):
        return llm_output.content
    if isinstance(llm_output, str):
        return llm_output
    if isinstance(llm_output, dict):
        return llm_output.get('content', str(llm_output))
    return str(llm_output)

# ── Setup ─────────────────────────────────────────────────────
load_dotenv(find_dotenv())
language = os.environ['USE_LANGUAGE']
city = os.environ['CITY']
personality = os.getenv('PERSONALITY')
notifications_hook = os.getenv('NOTIFICATIONS_HOOK')

current_dir = os.path.dirname(os.path.realpath(__file__))

def _load_prompt(filename):
    with open(f'{current_dir}/prompts/{filename}', 'r', encoding='utf-8') as f:
        return PromptTemplate.from_template(f.read())

analyzer_prompt = _load_prompt('analyzer.prompt')
commander_s1_prompt = _load_prompt('commander_step1.prompt')
commander_s2_prompt = _load_prompt('commander_step2.prompt')
writer_prompt = _load_prompt('writer.prompt')

pushbullet_key = os.getenv('PUSHBULLET_API_KEY')
pushbullet = Pushbullet(pushbullet_key) if pushbullet_key else None

# ── LLMs ──────────────────────────────────────────────────────
Analyzer = create_llm(temperature=0)
Commander = create_llm(temperature=0.3)
Writer = create_llm(temperature=0.5)

# All chains: prompt → LLM → text output (NO function calling)
analyzer_chain = analyzer_prompt | Analyzer | RunnableLambda(_get_text)
writer_chain = writer_prompt | Writer | RunnableLambda(_get_text)

def commander_chain(future_step):
    prompt = commander_s1_prompt if future_step == 'step1' else commander_s2_prompt
    return prompt | Commander | RunnableLambda(_get_text)


def _extract_json(text):
    """Robust JSON extraction from LLM text output.
    Handles markdown fences, stray text before/after JSON."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code fences
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding the first { ... } block
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f'Could not extract JSON from: {text[:200]}')


def _invoke_json(chain, args, module_name=''):
    """Invoke a text chain and extract JSON from the output."""
    raw = chain.invoke(args)
    if not raw or not raw.strip():
        raise ValueError(f'{module_name} returned empty response')
    result = _extract_json(raw)
    print(f'[{module_name}] OK')
    return result


@retry(stop=stop_after_attempt(3), wait=wait_fixed(90))
def _invoke_with_retry(chain, args, name=''):
    try:
        return _invoke_json(chain, args, name)
    except Exception as e:
        print(f'[retry] {name}: {type(e).__name__}: {e}')
        traceback.print_exc()
        raise


# ── Main entry ────────────────────────────────────────────────

def respond_to_girl(name_age, messages):
    previous_summary = get_record(name_age)

    # 1. Analyze conversation state
    analyzer_out = _invoke_with_retry(
        analyzer_chain,
        {'summary': previous_summary, 'messages': messages},
        'Analyzer',
    )
    future_step = analyzer_out.get('future_step', 'step1')
    summary = analyzer_out.get('summary', '')
    contact = analyzer_out.get('contact', '')

    # 2. If she gave contact info → notify and stop
    if contact:
        if notifications_hook:
            requests.get(notifications_hook, params={'name_age': name_age, 'contact': contact})
        if pushbullet:
            pushbullet.push_note(f'Date planned with {name_age}', contact)
        upsert_record(name_age, not_to_rise=True)
        return None

    # 3. Commander picks strategy tags
    commander_out = _invoke_with_retry(
        commander_chain(future_step),
        {'summary': summary, 'messages': messages},
        'Commander',
    )
    tags = commander_out.get('tags', [])
    rules = '\n###\n- '.join([query_rule(tag) for tag in tags])

    # 4. Writer generates the actual reply
    writer_out_raw = writer_chain.invoke({
        'rules': rules,
        'messages': messages,
        'summary': summary,
        'language': language,
        'city': city,
        'personality': personality,
    })
    try:
        writer_out = _extract_json(writer_out_raw)
    except ValueError:
        # Writer sometimes returns plain text instead of JSON
        writer_out = {'reasoning': '', 'messages': [writer_out_raw.strip()]}

    messages_to_send = writer_out.get('messages', [])
    if isinstance(messages_to_send, str):
        messages_to_send = [messages_to_send]

    # 5. If we told a story or built image, re-analyze summary
    if 'Attractive guy image' in tags or 'Storytelling' in tags:
        a2 = _invoke_with_retry(
            analyzer_chain,
            {'summary': summary, 'messages': f'Conversator: {messages_to_send}'},
            'Analyzer(2)',
        )
        summary = a2.get('summary', summary)

    upsert_record(name_age, summary)
    return messages_to_send
