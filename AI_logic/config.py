"""
Auto-detect LLM credentials from Claude Code config (~/.claude/settings.json).
Falls back to .env variables for manual override.
"""
import os
import json
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def _read_claude_settings():
    """Parse ~/.claude/settings.json and return the 'env' dict."""
    settings_path = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f).get('env', {})
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


_claude_env = _read_claude_settings()

# Resolve API key: .env takes priority, then Claude settings, then env var
API_KEY = (
    os.getenv('OPENAI_API_KEY')
    or _claude_env.get('ANTHROPIC_AUTH_TOKEN')
    or os.getenv('ANTHROPIC_AUTH_TOKEN')
    or ''
)

# Resolve base URL: convert Anthropic endpoint to OpenAI-compatible
_raw_base = os.getenv('OPENAI_BASE_URL') or os.getenv('ANTHROPIC_BASE_URL') or ''
if 'api.deepseek.com/anthropic' in _raw_base:
    _raw_base = 'https://api.deepseek.com/v1'
elif 'api.deepseek.com' in _raw_base and '/v1' not in _raw_base:
    _raw_base = _raw_base.rstrip('/') + '/v1'
BASE_URL = _raw_base or 'https://api.deepseek.com/v1'

# Default model — override via OPENAI_MODEL in .env
MODEL = os.getenv('OPENAI_MODEL') or os.getenv('ANTHROPIC_MODEL') or 'deepseek-chat'


def create_llm(temperature=0.0, model=None):
    """Factory: returns a ChatOpenAI instance wired to the detected API."""
    from langchain.chat_models import ChatOpenAI
    return ChatOpenAI(
        model=model or MODEL,
        temperature=temperature,
        openai_api_key=API_KEY,
        openai_api_base=BASE_URL,
    )


# Print config summary on import (helps debugging)
print(f'[config] API_BASE={BASE_URL}  MODEL={MODEL}  KEY={"***" + API_KEY[-4:] if API_KEY else "MISSING"}')
