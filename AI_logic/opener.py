import os
import json
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_fixed
from dotenv import load_dotenv, find_dotenv
from AI_logic.config import create_llm


# API keys import
load_dotenv(find_dotenv())
language = os.environ['USE_LANGUAGE']

current_dir = os.path.dirname(os.path.realpath(__file__))
with open(f'{current_dir}/prompts/opener.prompt', 'r', encoding='utf-8') as file:
    prompt_template = file.read()

prompt = PromptTemplate.from_template(prompt_template)

llm = create_llm(temperature=0.5)

chain = prompt | llm | StrOutputParser()

def log_retry(retry_state):
    print("No response from LLM. Retrying...")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(90), before_sleep=log_retry)
def generate_opener(name, description):
    raw = chain.invoke({'name': name, 'description': description, 'language': language})
    # The LLM sometimes returns a JSON array ["message"], sometimes plain text.
    # Normalise to a list of message strings.
    if isinstance(raw, list):
        return raw
    raw = raw.strip()
    if raw.startswith('[') and raw.endswith(']'):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    return [raw]
