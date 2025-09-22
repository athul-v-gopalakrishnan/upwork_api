from dotenv import load_dotenv
from typing import Sequence
from typing_extensions import Annotated, TypedDict, List, Optional
from pydantic import BaseModel,Field

from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.tools import tool
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from vault.db_config import DB_CONNECTION_STRING

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import SystemMessage,BaseMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
  
class Milestone(BaseModel):
    title: str = Field(..., description="Title of the milestone")
    amount: float = Field(..., description="Amount for the milestone")
    due_date: str = Field(..., description="Due date for the milestone in YYYY-MM-DD format")
    
class QuestionAnswer(BaseModel):
    question: str = Field(..., description="The question asked by the client in the job posting")
    answer: str = Field(..., description="Your answer to the question")
    
class Proposal(BaseModel):
    cover_letter: str = Field(..., description="A well formatted cover letter for the job proposal.")
    questions_and_answers: List[QuestionAnswer] = Field(default_factory=list , description="List of questions and your answers")
    
class State(TypedDict):
    messages:Annotated[Sequence[BaseMessage],add_messages]
    rag_query:Optional[str]
    proposal:Optional[Proposal]
    project_details:Optional[str]
    retrieved_projects:Optional[str]
    
llm_name = "openai:gpt-5"

llm = init_chat_model(llm_name)
retriever_llm = init_chat_model("openai:gpt-5-nano")
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
memory = MemorySaver()

RETRIEVAL_SYSTEM_PROMPT = """
            You are a specialized query generator for an Upwork proposal system.

            Your ONLY task: 
            - Convert the client's project description into a broad, semantically meaningful query.
            - Pass this query into the "retrieval" tool to search past projects.
            - Return only the query text (no explanations, no formatting).

            ## Rules (in order of importance):
            1. Output must be a single short query string.
            2. Focus on the main technical or conceptual problem.
            3. Generalize appropriately (e.g., "recommendation systems" instead of "clothing app recommender").
            4. Avoid copying the client's words exactly unless they already describe the general concept.
            5. If multiple themes exist, choose the dominant technical one.

            ## Examples:
            Client: "I need a recommendation engine for a clothing app."
            Query: recommendation systems

            Client: "Automating invoices in Excel with some Python scripting."
            Query: workflow automation and financial data processing

            Client: "Looking for someone to build a chatbot for healthcare queries."
            Query: conversational AI for healthcare

            Client: "We want to analyze customer reviews to find pain points in our product."
            Query: sentiment analysis and customer feedback mining

            Client: "Build an ETL pipeline to move data from MongoDB to BigQuery."
            Query: ETL pipelines and database integration
"""



PROPOSAL_SYSTEM_PROMPT = """
            You are an expert proposal writer for an Upwork agency.

            Your task is to generate customized, professional proposals for new client projects.  
            You will be given:
            1. The project details will be given as a well structured and detailed json.
            2. A list of relevant past projects retrieved from a vector database (with metadata such as industry, technology, and domain).

            ## Rules (in order of importance):

            1. **Schema Compliance**
            - The output MUST strictly follow the "Proposal" schema.
            - "cover_letter" must be a professional, well-structured cover letter. 
            - "questions_and_answers" should only be included if the project details json has the some questions in the questions field. While generating the answers, use the model "QuestionAnswer" \
                in the "questions_and_answers" field of the "Proposal" schema. The question should exactly match the question given in the json.

            2. **Use of Past Projects**
            - Use the retrieved past projects and metadata as references to demonstrate expertise.
            - Choose examples based on industry, domain, or technology alignment.
            - If no useful projects are retrieved, simply write the proposal without referencing them.
            - Never fabricate past projects.

            3. **Client Questions**
            - If the client asks questions in the project description field in the json given, include the answer in the cover letter.
            - The answers to the questions in the questions field should be in the "questions_and_answers" field of the "Proposal" schema.
            - If no questions are asked, leave "questions_and_answers" field empty.

            4. **Cover Letter Quality**
            - Be persuasive, client-focused, and confident.
            - Highlight relevant experience and strengths.
            - Show how the agency will solve the client's problem.
            - Keep formatting clean and easy to read.
            - Use the "Cover Letter" fields based on industry, domain, or technology given in the metadata of the extracted projects to create a new cover letter of the project. 
            - Follow the schema and the approach in the given example.

            ## Example Behaviors:
            - Client asks: "Have you built dashboards before?" → Answer in "questions_and_answers".
            - Retrieved project about "workflow automation in finance" → Reference it for "invoice automation".
            - No relevant projects retrieved → Write a professional proposal without references.

            ## Output Format:
            Strictly produce output in the "Proposal" schema.
"""

def retrieve(
    state:State,
    ):
    rag_query = state.get("rag_query", "")
    retriever = PGVector(
            embeddings=embedding_model,
            collection_name="proposal_embeddings",
            connection=DB_CONNECTION_STRING
        )
    retrieved_docs = retriever.similarity_search(query = rag_query, k = 5)
    serialised = "\n\n".join(
        (f"Source : {doc.metadata}\nProject Description:{doc.page_content}")
        for doc in retrieved_docs
    )
    return {
        "retrieved_projects": serialised,
        "messages":state["messages"] + [AIMessage(content=serialised)],
    }

bidder_llm = llm.with_structured_output(Proposal)

def check_for_tool_calls(state:State):
    last_message = state["messages"][-1]
    print(hasattr(last_message, "tool_calls") and bool(last_message.tool_calls))
    return (hasattr(last_message, "tool_calls") and bool(last_message.tool_calls))

def generate_search_query(state:State):
    project_details = state.get("project_details", "")
    
    prompt = [
        SystemMessage(content=RETRIEVAL_SYSTEM_PROMPT),
        HumanMessage(content=f"The project details are given below:\n{project_details}")
    ]
    response = retriever_llm.invoke(prompt)
    return {
        "rag_query":response.content,
        "messages":state["messages"] + [AIMessage(content=response.content)]
        }
    
def generate_propsal(state:State):
    project_details = state.get("project_details", "")
    retrieved_projects = state.get("retrieved_projects", "")
    prompt = [
        SystemMessage(content=PROPOSAL_SYSTEM_PROMPT),
        HumanMessage(content=f"The project details are given below:\n{project_details}\n\nThe past relevant projects are given below:\n{retrieved_projects}")
    ]
    response = bidder_llm.invoke(prompt)
    return {
        "proposal":response,
        "messages":state["messages"] + [AIMessage(content=response.model_dump_json(indent=2))]
        }

def build_bidder_agent(checkpointer)->StateGraph:
    graph_builder = StateGraph(State)
    graph_builder.add_node(generate_search_query)
    graph_builder.add_node(retrieve)
    graph_builder.add_node(generate_propsal)
    graph_builder.set_entry_point("generate_search_query")
    graph_builder.add_edge("generate_search_query", "retrieve")
    graph_builder.add_edge("retrieve", "generate_propsal")
    graph_builder.set_finish_point("generate_propsal")
    graph = graph_builder.compile(checkpointer=checkpointer, )
    return graph

def call_proposal_generator_agent(agent:StateGraph, project_description:str):
    initial_state:State = {
        "messages":[HumanMessage(content=f"The project details are given below:\n{project_description}")],
        "project_details":project_description,
    }
    final_state = agent.invoke(initial_state, config={
                    "configurable": {
                        "thread_id": "user123",
                    }})
    generated_proposal =  final_state["proposal"]
    
    response = {
        "llm_name": f"Hi I am {llm_name}",
        "cover_letter": generated_proposal.cover_letter,
        "questions_and_answers": [{"question": qa.question, "answer": qa.answer} for qa in generated_proposal.questions_and_answers]
    }
    
    return response
    
    

if __name__ == "__main__":
    agent = build_bidder_agent()
    generated_proposal = call_proposal_generator_agent(agent, "I need a recommendation engine for a clothing app. Have you built recommendation systems before?")
    print(generated_proposal["cover_letter"])
    for questions_and_answers in generated_proposal["questions_and_answers"]:
        print(f"Q: {questions_and_answers["question"]}\nA: {questions_and_answers["answer"]}\n")