# Single-cell OpenAI LangChain chatbot example

import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

# 1️⃣ Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env")
print("OpenAI API Key loaded:", api_key[:25] + "...")

# 2️⃣ Initialize OpenAI model
model = init_chat_model("gpt-4o-mini", model_provider="openai")

# 3️⃣ Define prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that explains concepts simply."),
    ("human", "{question}")
])

# 4️⃣ Example single-turn query
question = "What is LangChain?"
final_prompt = prompt.invoke({"question": question})
response = model.invoke(final_prompt)
print("Single-turn Response:\n", response.content)

# 5️⃣ Example multi-turn conversation
messages = [
    HumanMessage(content="Hi! I'm Alice."),
    AIMessage(content="Hello Alice! How can I help you today?"),
    HumanMessage(content="Can you explain what LangChain is?")
]
multi_response = model.invoke(messages)
print("\nMulti-turn Response:\n", multi_response.content)