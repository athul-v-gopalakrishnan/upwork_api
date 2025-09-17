from dotenv import load_dotenv
from typing import Sequence
from typing_extensions import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.tools import tool
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from vault.db_config import DB_CONNECTION_STRING

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage,BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

class State(TypedDict):
    messages:Annotated[Sequence[BaseMessage],add_messages]
    # doc:str
    temperature:float

llm = init_chat_model("openai:gpt-5-mini")
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
memory = MemorySaver()
prompt_template = ChatPromptTemplate.from_template("""
        TThe client has posted the following project description:

        {project_description}

        Your tasks:
        1. Analyze the description and identify the core problem in broad, general terms.  
        2. Use the `retrieve` tool with that conceptual problem to find relevant past projects.  
        3. Write a proposal with the following structure:
        - **Introduction:** Show you understand the client's needs.  
        - **Relevant Experience:** Summarize related past projects (from the retrieved context) and show how they connect conceptually.  
        - **Proposed Approach:** Briefly describe your plan to solve the client's problem.  
        - **Value Proposition:** Explain why our agency is uniquely suited.  
        - **Call to Action:** Invite the client to discuss further.  

        Constraints:
        - Be concise (250-350 words).  
        - Use natural, professional language.  
        - Do not copy project descriptions verbatim; reinterpret them in the client's context.  
 
"""
)

SYSTEM_PROMPT = """You are an expert proposal writer for an Upwork agency.
                    Your goal is to generate customized, professional proposals for new client projects.
                    You have access to a tool called **retrieve** that lets you search a vector database of past agency projects.
                    Use this tool whenever you need to find relevant prior work that demonstrates expertise aligned with the client's project.
                    Always query the tool with a broad conceptual problem statement, not just keywords, so that you retrieve projects that are semantically and technically relevant.
                    For example:

                    If the client asks for “a recommendation engine for a clothing app,” query the tool with “personalized recommendation systems for consumer apps.”

                    If the client asks for “automating invoices in Excel,” query with “workflow automation and financial data processing.”
                    
                    **Important:** If you cannnot find relevant past projects in one tool call, try rephrasing your query and calling the tool again.
                    **Do not make up past projects; only use what you retrieve from the tool.**"""

@tool(response_format="content", description="Retrieve of data past projects using the project description from vector store")
def retrieve(
    query:str,
    ):
    retriever = PGVector(
            embeddings=embedding_model,
            collection_name="proposal_embeddings",
            connection=DB_CONNECTION_STRING
        )
    retrieved_docs = retriever.similarity_search(query = query, k = 5)
    serialised = "\n\n".join(
        (f"Source : {doc.metadata}\nProject Description:{doc.page_content}")
        for doc in retrieved_docs
    )
    return serialised

retrieve_tool = ToolNode(tools=[retrieve], name="retrieve_node")
bidder_llm = llm.bind_tools(tools = [retrieve], tool_choice="auto")

def check_for_tool_calls(state:State):
    last_message = state["messages"][-1]
    print(hasattr(last_message, "tool_calls") and bool(last_message.tool_calls))
    return (hasattr(last_message, "tool_calls") and bool(last_message.tool_calls))

def query_or_respond(state:State):
    prompt = prompt_template.invoke({
        "project_description":state["messages"]
    })
    response = bidder_llm.invoke(prompt)
    return {"messages":[response]}

def build_bidder_agent():
    graph_builder = StateGraph(State)
    graph_builder.add_node(query_or_respond)
    graph_builder.add_node(retrieve_tool)
    graph_builder.set_entry_point("query_or_respond")
    graph_builder.add_conditional_edges(
        "query_or_respond",
        check_for_tool_calls,
        {False:END, True:"retrieve_node"}
    )
    graph_builder.add_edge("retrieve_node", "query_or_respond")
    graph = graph_builder.compile(checkpointer=memory, )
    return graph

def generate_proposal(agent:StateGraph, project_description:str):
    initial_state:State = {
        "messages":[SystemMessage(content=SYSTEM_PROMPT)],
        "temperature":0.2
    }
    initial_state["messages"].append(
        SystemMessage(content=f"Write a proposal for the following project description:\n{project_description}")
    )
    final_state = agent.invoke(initial_state, config={
                    "recursion_limit": 3,
                    "configurable": {
                        "thread_id": "user123",
                    }})
    return final_state["messages"][-1].content
    

if __name__ == "__main__":
    agent = build_bidder_agent()
    initial_state:State = {
        "messages":[SystemMessage(content=SYSTEM_PROMPT)],
        "temperature":0.2
    }
    query = """We need a web application that allows users to create and share photo albums with friends. 
    The app should support user authentication, photo uploads, album creation, and social sharing features."""
    initial_state["messages"].append(
        SystemMessage(content=f"Write a proposal for the following project description:\n{query}")
    )
    final_state = agent.invoke(initial_state, config={
                "configurable": {
                    "thread_id": "user123",
                }})
    print(final_state["messages"][-1].content)