from dotenv import load_dotenv, find_dotenv
import os
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from AI_logic.config import create_llm


load_dotenv(find_dotenv())
language = os.environ['USE_LANGUAGE']


def translate_rise_msg(message):
    prompt = ("Translate message to {language}, leave same style and emoticons. Message is directed to woman."
              "\n\nMessage: {message}")
    prompt = PromptTemplate.from_template(prompt)
    llm = create_llm(temperature=0.5)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({'message': message, 'language': language})
