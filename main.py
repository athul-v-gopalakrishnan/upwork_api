from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import traceback
import pickle
import asyncio
import json
import re
import os
from dotenv import load_dotenv

from nyx.browser import NyxBrowser

from upwork_agent.bidder_agent import build_bidder_agent,call_proposal_generator_agent, Proposal
from db_utils.db_pool import init_pool, close_pool
from db_utils.access_db import add_proposal, create_proposals_table, create_jobs_table, get_job_by_url
from db_utils.queue_manager import create_queue_table, enqueue_task, get_next_task, update_task_status, abort_tasks_on_restart
from utils import generate_search_links

from upwork_agent.scrape_jobs import ScraperSession
from upwork_agent.application import ApplicationSession

from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

LOGIN_USERNAME = os.getenv("UPWORK_USERNAME")
LOGIN_PASSWORD = os.getenv("UPWORK_PASSWORD")
SECURITY_QUESTION_ANSWER = os.getenv("UPWORK_SECURITY_QUESTION_ANSWER")

state = {}
latest_urls_path = 'latest_links.pkl'
if os.path.exists(latest_urls_path):
    print("Loading latest URLs from", latest_urls_path)
    with open(latest_urls_path, 'rb') as f:
        latest_urls = pickle.load(f)
    print("Latest URLs loaded:", latest_urls)
else:
    print("No latest URLs file found, initializing with None values.")
    latest_urls = {
        "Frontend" : None,
        "Backend" : None,
        "Fullstack" : None,
        "Mobile" : None,
        "AI/ML" : None,
        "GenAI" : None,
        "Devops" : None,
        "IOT" : None,
        "Low code/No code" : None,
        "Non Tech" : None,
        "Data Engineering" : None,
        "Business Intelligence" : None,
        "Best Match" : None
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    browser = NyxBrowser()
    await browser.start()
    state['browser'] = browser
    print("Browser started")
    state["filter_urls"] = generate_search_links()
    state["latest_urls"] = latest_urls
    page = await state.get("browser").new_page()
    state["page"] = page
    await init_pool()
    print("Database pool initialized")
    # cm = PostgresSaver.from_conn_string(MEMORYDB_CONNECTION_STRING)
    # state["checkpointer"] = cm.__enter__()
    # state["checkpointer"].setup()
    cm = MemorySaver()
    state["checkpointer"] = cm
    state["bidder_agent"] = build_bidder_agent(state["checkpointer"])
    print("Bidder agent created")
    state["application_underway"] = False
    proposal_table_status, msg = await create_proposals_table()
    print(proposal_table_status, msg)
    job_table_status, msg = await create_jobs_table()
    print(job_table_status, msg)
    task_queue_table_status, msg = await create_queue_table()
    print(task_queue_table_status, msg)
    abort_status, msg = await abort_tasks_on_restart()
    print(abort_status, msg)
    worker_task = asyncio.create_task(worker_loop())
    print("Worker loop started")
    yield
    # Shutdown code
    # cm.__exit__(None, None, None)
    worker_task.cancel()
    await close_pool()
    print("Database pool closed")
    await browser.shutdown()

state["last_url"] = ""
    
app = FastAPI(
    title="Upwork API",
    description="An upwork automation bot with intelligence and captcha solving capabilities.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:5678",
    "http://127.0.0.1:5678",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/enqueue_task")
async def enqueue_task_api(task_type:str, payload = None, priority:int=0):
    print(f"Enqueuing task: {task_type} with payload: {payload} and priority: {priority}")
    status, message = await enqueue_task(task_type=task_type, payload=payload, priority=priority)
    return {"status" : status, "message" : message}

async def check_for_jobs(task_id:int):
    session = ScraperSession(
            task_id=task_id,
            page = state["page"], 
            links_to_visit=state["filter_urls"], 
            last_links=state["latest_urls"], 
            username= LOGIN_USERNAME, 
            password=LOGIN_PASSWORD, 
            security_answer=SECURITY_QUESTION_ANSWER
        )
    await session.run()

@app.post("/generate_proposal")
async def generate_proposal_api(job_url:str):
    job_uuid, job_details = await get_job_by_url(job_url=job_url)
    if not job_details:
        return {"status" : "Failed", "message" : "Job details not found in database."}
    job_type = job_details.get("job_type","Unknown")
    print(f"Generating proposal for job type: {job_type}")
    job_details = json.dumps(job_details)
    print(f"Job Details: {job_details}")
    proposal, proposal_model = await call_proposal_generator_agent(state["bidder_agent"], job_details)
    payload = {
        "status" : "Done",
        "job_type" : job_type,
        "job_url" : job_url,
        "proposal" : proposal
    }
    response = await add_proposal(uuid = job_uuid,job_url=job_url, job_type=job_type, proposal = proposal_model, applied=False)
    if response:
        return payload
    else:
        print(response)
        return response
    

async def apply_for_job(task_id:int,job_url: str, human:str = "Unable to verify"):
    session = ApplicationSession(
            task_id=task_id,
            page = state["page"], 
            job_url=job_url,
            username= LOGIN_USERNAME, 
            password=LOGIN_PASSWORD, 
            security_answer=SECURITY_QUESTION_ANSWER , 
            human=human
        )
    await session.run()
            
        
def question_answer_parser(proposal:Proposal):
    q_a_dict = {}
    for question_and_answer in proposal.questions_and_answers:
        question = re.sub(r"^\d+\.\s*", "", question_and_answer.question.strip())
        answer = question_and_answer.answer.strip()
        q_a_dict[question] = answer
    return q_a_dict


async def worker_loop():
    while True:
        try:
            status,task = await get_next_task()
            if status:
                task_id = task['id']
                task_type = task['task_type']
                print(f"Processing task: {task_type}")
                for key, value in task.items():
                    print(f"{key}: {value}")
                if task_type == 'check_for_jobs':
                    await check_for_jobs(task_id=task_id)
                    await update_task_status(task_id=task_id, status='done')
                elif task_type == 'apply_for_job':
                    payload_string = task.get("payload","")
                    payload = json.loads(payload_string) if payload_string else {}
                    job_url = payload.get("job_url", "")
                    if job_url:
                        await apply_for_job(task_id=task_id,job_url=job_url)
            else:
                print("No tasks in queue, waiting...")
        except Exception as e:
            print(f"Error in worker loop: {e}")
            traceback.print_exc()
        finally:
            await asyncio.sleep(3)

if __name__ == "__main__":
    hehe = asyncio.run(question_answer_parser("https://www.upwork.com/jobs/~021970706874169818481?link=new_job&frkscc=NYf13dCiTalJ"))
    print(hehe)