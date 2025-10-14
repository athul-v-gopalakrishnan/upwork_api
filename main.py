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
from db_utils.queue_manager import create_queue_table, enqueue_task, get_next_task

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
    with open(latest_urls_path, 'rb') as f:
        latest_urls = pickle.load(f)
else:
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
    state["filter_urls"] = {
        "Frontend" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&q=angular%20OR%20React%20OR%20Javascript%20OR%20Typescript&sort=recency&t=0,1",
        "Backend" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=2,3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&q=NodeJS%20OR%20Golang%20OR%20Python%20OR%20Database%20OR%20MongoDB%20OR%20SQL%20OR%20postgresql%20OR%20API%20Integration&sort=recency&t=0,1",
        "Fullstack" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=MEAN%20OR%20MERN%20OR%20Fullstack%20OR%20MongoDB&sort=recency&t=0,1",
        "Mobile" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=%22React%20Native%22%20OR%20Flutter%20OR%20PWA%20OR%20%22%20Progressive%20Web%20App%22&sort=recency&t=0,1",
        "AI/ML" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=natural%20language%20processing%20or%20nlp%20or%20tensorflow%20or%20opencv%20or%20mlops%20or%20ml%20or%20machine%20learning%20or%20chatbot&sort=recency&t=0,1",
        "GenAI" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=artificial%20intelligence%20or%20ai%20agent%20or%20ai%20or%20agenti%20ai%20or%20rag%20or%20llm%20or%20large%20language%20model%20or%20data%20science%20or%20open%20ai&sort=recency&t=0,1",
        "Devops" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=Docker%20OR%20Pineline%20OR%20CI%2FCD%20OR%20AWS%20OR%20GCP%20OR%20Azure%20OR%20Monitoring%20OR%20Prometheus%20OR%20Grafana%20OR%20Kubernetes&sort=recency&t=0,1",
        "IOT" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=IoT%20OR%20Internet%20of%20Things&sort=recency&t=0,1",
        "Low code/No code" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=2,3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=Bubble%20OR%20Webflow&sort=recency&t=0,1",
        "Non Tech" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=2,3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=web%20OR%20development%20OR%20software%20OR%20Mobile%20OR%20MVP%20OR%20SAAS%20OR%20Startup%20OR%20AI&sort=recency&t=0,1",
        "Data Engineering" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=power%20bi%20or%20data%20engineering%20or%20snowflake%20or%20dashboard&sort=recency&t=0,1",
        "Business Intelligence" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=week,month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=data%20analysis%20or%20data%20analyst%20or%20quicksight%20or%20etl%20or%20elt%20or%20dax%20or%20data%20lakehouse%20or%20sql%20or%20bi%20or%20ai%20byte%20or%20business%20intelligence&sort=recency&t=0,1"
    }
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

async def check_for_jobs():
    session = ScraperSession(
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
    job_details = await get_job_by_url(job_url=job_url)
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
    response = await add_proposal(job_url=job_url, job_type=job_type, proposal = proposal_model, applied=False)
    if response:
        return payload
    else:
        print(response)
        return response
    

async def apply_for_job(job_url: str, human:str = "Unable to verify"):
    session = ApplicationSession(
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
                task_type = task['task_type']
                print(f"Processing task: {task_type}")
                for key, value in task.items():
                    print(f"{key}: {value}")
                if task_type == 'check_for_jobs':
                    await check_for_jobs()
                elif task_type == 'apply_for_job':
                    payload_string = task.get("payload","")
                    payload = json.loads(payload_string) if payload_string else {}
                    job_url = payload.get("job_url", "")
                    if job_url:
                        await apply_for_job(job_url=job_url)
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