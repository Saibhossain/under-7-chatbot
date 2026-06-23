import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()

model = os.getenv("MODEL")
print(model)

LLM_MODEL = "gpt-4.1-nano-2025-04-14"

llm = ChatOpenAI(
    model=LLM_MODEL, 
    temperature=0.7,
    max_retries=2
)