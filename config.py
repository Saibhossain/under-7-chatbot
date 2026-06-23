import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()




LLM_MODEL = os.getenv("MODEL")

llm = ChatOpenAI(
    model=LLM_MODEL, 
    temperature=0.0,
    max_retries=2
)