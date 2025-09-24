from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.tools import tool
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from vault.db_config import DB_CONNECTION_STRING
from utils.models import *

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import SystemMessage,BaseMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
    
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
            Your goal is to generate customized, professional proposals for new client projects.  

            You will be given:
            1. A JSON object called "project_details" containing a well-structured project description, metadata, and optional client questions.
            2. A JSON array called "selected_projects" containing relevant past projects retrieved from a vector database (with metadata such as industry, technology, and domain).

            ---

            ## Rules (in order of importance):

            ### 1. Schema Compliance
            The output MUST strictly follow the "Proposal" schema:
            "cover_letter" must be a professional, well-structured cover letter. 
            "questions_and_answers" should only be included if the "project_details" JSON has questions. 
            Each question in "project_details" → must exactly match in "questions_and_answers".  

            ---

            ### 2. Project Type Classification
            Analyze "project_details.description" and classify into:
            - "role-based" → ongoing or long-term roles (e.g., “We need a DevOps engineer…”)
            - "project-based" → fixed-scope, outcome-driven (e.g., “We need to build an API…”)
            - "team-based" → collaborative or agency-style (e.g., “Join our development team…”)

            ---

            ### 3. First Line Generation (Dynamic Hooks)
            The **first line of the cover letter** must be dynamically generated based on the classified project type.  
            It must feel natural, **not templated or repeated**, and should adapt intelligently to the client’s JD.  
            Follow these intent-based rules (always paraphrase and vary wording):  

            🔹 **Role-Based (individual expertise)**  
            Highlight direct alignment of your skills/experience with the role.  
            Show confidence that you can contribute effectively from day one.  
            Example intent (paraphrase, don't copy):  
            - “This role strongly aligns with my background in [skills/technologies].”  
            - “Your requirement for [role/skills] resonates directly with my expertise.”  

            🔹 **Project-Based (specific deliverables/outcomes)**  
            Show excitement about the project's scope and goals.  
            Connect to past experiences delivering similar outcomes.  
            Example intent (paraphrase, don't copy):  
            - “Your project to [deliverable/goal] immediately caught my attention.”  
            - “The goal of creating [system/feature] fits perfectly with my past experience.”  

            🔹 **Team-Based (collaboration/agency support)**  
            Emphasize collaborative delivery and multi-skill coverage.  
            Highlight ability to provide end-to-end team support.  
            Example intent (paraphrase, don't copy):  
            - “With our team's combined expertise, we can cover every aspect of your platform's development.”  
            - “Your project requires diverse skills, and we can provide a complete team to ensure success.”  

            Always generate a **natural, non-repetitive variation** of these ideas rather than copying examples verbatim.  

            ---

            ### 4. Second Line (Credibility Anchor)
            Immediately after the first line, generate a **second line** that establishes credibility.  
            Select the **top 2 past projects** from "selected_projects" that best match the client's JD.  
            For each project, describe in one sentence:  
            • The tech stack used  
            • The core problem faced  
            • The solution implemented  
            • The outcome/impact delivered  
            Write each as a **natural flowing sentence** (not bullets).  
            These two sentences together should form a **strong evidence paragraph** that mirrors the client's JD requirements.  

            ---

            ### 5. Third Line (Problem-Focused)
            After the credibility anchor, add a **third line or short paragraph** that is problem-centric:  
            - If the JD explicitly mentions a pain point, challenge, or concern, reference it directly.  
            - If no explicit problem is mentioned, intelligently infer the likely core challenge from the JD context.  
            - Phrase it from the **client's perspective** (not just past projects).  
            - Continue the line by saying you have delivered solutions for such challenges and briefly highlight your expertise/approach.  
            This line should be distinct from the first two lines.  

            ---

            ### 6. Fourth Line (Call-to-Action / Demo or Call)
            After the problem-focused third line, add a **fourth line** that is a **friendly, actionable CTA**:  
            - Examples of phrasing (always vary wording naturally):  
            - “Can I share a quick Loom demo with some ideas for your project?”  
            - “Can I share a quick Loom demo of how I've built chat + voice AI agents that improved response times and reduced lead loss?”  
            - “Can we hop on a quick call to discuss the project further?”  
            Ensure this line feels **personal, confident, and engaging**, prompting the client to take the next step.  

            ---

            ### 7. Use of Past Projects
            Use the "selected_projects" and metadata as references to demonstrate expertise.  
            If no relevant projects exist, skip the references and write a strong proposal anyway.  
            Never fabricate past projects.  

            ---

            ### 8. Client Questions
            If the client asks questions directly in the description, address them naturally in the cover letter.  
            If the "project_details" JSON has a "questions" field, answer them in "questions_and_answers".  
            Each question text must match exactly.  
            If no questions exist, leave "questions_and_answers" as an empty array.  

            ---

            ### 9. Cover Letter Body
            After the first, second, third, and fourth lines, continue with a professional, persuasive body:
            - Highlight broader relevant experience and strengths.  
            - Show how the agency will solve the client's problem.  
            - Emphasize client benefits (scalability, reliability, cost efficiency, faster delivery, etc.).  
            - Keep formatting clean and easy to read.  
            - Maintain word count around 200-300 words.  
            Match tone and structure to the project type (role/project/team).  

            ---

            ## Output:
            Return only a JSON object following the "Proposal" schema with two fields:
            1. "cover_letter" → A professional, customized cover letter with:  
            - A **dynamic first line** (hook)  
            - A **second line credibility anchor** (top 2 past projects)  
            - A **third line problem-focused reassurance**  
            - A **fourth line CTA** (demo or call)  
            - A persuasive continuation + closing  
            2. "questions_and_answers" → Array of {question, answer}, or empty if none.
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
    
    return response, generated_proposal
    
    

if __name__ == "__main__":
    agent = build_bidder_agent()
    generated_proposal = call_proposal_generator_agent(agent, "I need a recommendation engine for a clothing app. Have you built recommendation systems before?")
    print(generated_proposal["cover_letter"])
    for questions_and_answers in generated_proposal["questions_and_answers"]:
        print(f"Q: {questions_and_answers["question"]}\nA: {questions_and_answers["answer"]}\n")