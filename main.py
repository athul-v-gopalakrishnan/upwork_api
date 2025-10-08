from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import traceback
import pickle
import asyncio
import httpx
import json
import re
import os

from nyx.browser import NyxBrowser
from nyx.page import NyxPage

from upwork_agent.bidder_agent import build_bidder_agent,call_proposal_generator_agent, Proposal
from vault.db_config import MEMORYDB_CONNECTION_STRING, dbname, username, password
from db_utils.db_pool import init_pool, close_pool
from db_utils.access_db import add_proposal, create_proposals_table, get_proposal_by_url, create_jobs_table, get_job_by_url, add_job
from db_utils.queue_manager import create_queue_table, enqueue_task, get_next_task
from utils.constants import send_job_updates_webhook_url, cloudfare_challenge_div_id, home_url, send_job_updates_webhook_url, upwork_url
from utils.job_filter import JobFilter

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver

state = {}
latest_urls_path = 'latest_urls.pkl'
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
    async with httpx.AsyncClient() as client:
        try:
            page = state["page"]
            login_status, message, num_jobs_scraped = await login_to_upwork(page=page, username="ali-maharuf", password="@neomaharuf124!", scrape_best=True, security_question_answer="Neoito")
            if not login_status:
                payload =  {"status" : "Failed", "message" : f"Login failed - {message}"}
                print(payload)
                await client.post(url = send_job_updates_webhook_url, json = payload)
            session_latest_links = {}
            new_jobs_num = num_jobs_scraped or 0
            
            job_filter = JobFilter()
            
            for category, url in state["filter_urls"].items():
                first_link = True
                await page.goto(url,wait_for = 'div[data-test="UpCInput"]', captcha_selector=cloudfare_challenge_div_id,wait_until= "domcontentloaded",referer="https://www.upwork.com/")
                job_postings = await page.get_all_elements(selector='article[data-test="JobTile"]')
                for job_posting in job_postings:
                    job_posted_time_elements = await job_posting.query_selector_all('small[data-test="job-pubilshed-date"] span')
                    job_posted_time = ""
                    for element in job_posted_time_elements:
                        job_posted_time += await page.get_text_content(element) + " "
                    link_div = await job_posting.query_selector('a[data-test="job-tile-title-link UpLink"]')
                    link = await link_div.get_attribute('href')
                    if not link:
                        payload = {"status": "Failed", "message":"Problem extracting link ... \nMaybe the website structure has changed"}
                        print(payload)
                        await client.post(url = send_job_updates_webhook_url, json = payload)
                        print("link_extraction_failed")
                        return 
                    link = upwork_url + link
                    if first_link:
                        session_latest_links[category] = link
                        first_link = False
                    job_posted_time = job_posted_time.lower().split(sep=" ")
                    if link == state["latest_urls"].get(category,None) or \
                        ("minutes" not in job_posted_time and "minute" not in job_posted_time) or \
                            ("seconds" not in job_posted_time and "second" not in job_posted_time):
                        print(f"last_link in {category}")
                        break
                    await page.click(link_div, wait_for='li[data-qa="client-location"] strong')
                    
                    status, job_details = await scrape_job(page=page)
                    print("checking job validity ...")
                    if not job_filter.is_job_allowed(job_details):
                        print("job not allowed by filter ...")
                        await page.go_back()
                        await asyncio.sleep(1)
                        continue
                    if status:
                        """Update db"""
                        job_update_status, msg = await add_job(job_url=link,job_description=job_details)
                        if not job_update_status and "duplicate key" in msg.get("message","").lower():
                            print(f"Job already exists in db - {link}")
                            await page.go_back()
                            await asyncio.sleep(1)
                            continue
                        elif not job_update_status:
                            await client.post(url = send_job_updates_webhook_url, json = msg)
                            print(f"db update error - {msg}")
                            return
                        else:
                            payload = {
                                "status" : "Done",
                                "category" : category,
                                "url" : link,
                                "job_details" : job_details
                            }
                            await client.post(url = send_job_updates_webhook_url, json = payload)
                            new_jobs_num += 1
                            print(f"job {new_jobs_num} sent.")
                    else:
                        job_details["url"] = link
                        await client.post(url = send_job_updates_webhook_url, json = job_details)
                        print(f"scraping failed - {job_details}")
                        
                    await page.go_back()
                    await asyncio.sleep(1)
                    
            state["latest_urls"] = session_latest_links 
            with open(latest_urls_path, 'wb') as f:
                print("Saving latest urls ...")
                pickle.dump(session_latest_links, f)   
            payload =  {"status" : "Check compelete.", "message" : f"Successfully checked for new jobs. {new_jobs_num} jobs found."}   
            print(payload)
            await client.post(url = send_job_updates_webhook_url, json = payload)
            return "done", "success"
        except Exception as e:
            payload =  {"status" : "Failed", "message" : f"Check failed. Error - {e}"}
            print(payload)
            traceback.print_exc()
            await client.post(url = send_job_updates_webhook_url, json = payload)
            return "failed", str(e)
        finally:
            await page.goto(home_url)

async def scrape_job(page:NyxPage):
    try:
        job_details = {}
        
        client_location = await page.get_text_content('li[data-qa="client-location"] strong')
        job_details["client_location"] = client_location.strip() if client_location else "N/A"
        
        if job_details["client_location"] == "N/A":
            job_details["status"] = "Failed"
            job_details["message"] = "Page loaded but failed to extract job details, possibility of a private job posting."
            return False, job_details
        
        hire_rate = await page.get_text_content('li[data-qa="client-job-posting-stats"] div')
        job_details["hire_rate"] = hire_rate.strip() if hire_rate else "N/A"
        
        total_spent = await page.get_text_content('li strong[data-qa="client-spend"] span span')
        job_details["total_spent"] = total_spent.strip() if total_spent else "N/A"
        
        member_since = await page.get_text_content('li[data-qa="client-contract-date"] small')
        job_details["member_since"] = member_since.strip() if member_since else "N/A"
        
        payment_verified = await page.check_for_element('div.payment-verified')
        print(f"Payment verified: {payment_verified}")
        job_details["payment_verified"] = payment_verified
        
        summary_element = await page.get_all_elements('div[data-test="Description"] p')
        summary = ""
        for element in summary_element:
            summary_chunk = await page.get_text_content(element)
            summary += summary_chunk.strip() + " "
        job_details["summary"] = summary.strip()
        
        duration_type_elements = await page.get_all_elements('div[data-cy*="duration"]')
        duration_elements = await page.get_all_elements('div[data-cy*="duration"] + strong > span')
        duration_type = await duration_type_elements[0].get_attribute('data-cy') if duration_type_elements else None
        duration = await page.get_text_content(duration_elements[0]) if duration_elements else "N/A"
        job_details["duration_type"] = duration_type.strip() if duration_type else "N/A"
        job_details["duration"] = duration.strip()
        
        price_div = await page.get_element('div[data-cy="fixed-price"] + div strong')
        if price_div:
            price = await page.get_text_content(price_div)
            job_details["hourly_rate"] = price.strip() if price else "N/A"
            job_details["job_type"] = "Fixed Price"
        else:        
            rate_divs = await page.get_all_elements('div[data-cy="clock-timelog"] + div strong')
            rates = []
            for div in rate_divs:
                rate = await page.get_text_content(div)
                rates.append(rate.strip())
            hourly_rate = "-".join(rates)
            job_details["hourly_rate"] = hourly_rate.strip() if hourly_rate else "N/A"
            job_details["job_type"] = "Hourly"
        
        skill_elements = await page.get_all_elements('div.skills-list span span a div div')
        skills = []
        for element in skill_elements:
            skill = await page.get_text_content(element)
            skills.append(skill.strip() + "\n")
        job_details["skills"] = ", ".join(skills)
        
        qualified = True
        if await page.check_for_element('ul.qualification-items'):
            qualification_elements = await page.get_all_elements('ul.qualification-items span.icons div')
            for element in qualification_elements:
                qualification_status = await page.get_attribute(element, 'title')
                if qualification_status == "You do not meet this qualification":
                    qualified = False
                    break
                
        job_details["qualified"] = qualified
        
        if await page.check_for_element('section[data-test="Questions"]'):
            question_number = 1
            questions = []
            question_elements = await page.get_all_elements('section[data-test="Questions"] ol li')
            for q_element in question_elements:
                question_text = await page.get_text_content(q_element)
                questions.append(str(question_number) + ". " + question_text.strip() + "\n")
                question_number+=1
            job_details["questions"] = " ".join(questions)
            print(job_details["questions"])
        else:
            job_details["questions"] = "N/A"
        print(job_details)
        return True, job_details
    except Exception as e:
        print(e)
        traceback.print_exc()
        await page.goto(home_url)
        return False, {"status": "Failed", "message": str(e)}

        
async def login_to_upwork(page:NyxPage,username: str, password: str, scrape_best:bool = False, security_question_answer: str = None, remember_me: bool = True):
    async with httpx.AsyncClient() as client:
        try: 
            await page.goto("https://www.upwork.com/ab/account-security/login",captcha_selector=cloudfare_challenge_div_id,wait_until= "domcontentloaded",referer="https://www.upwork.com") 
            login_page = await page.check_for_element("#login_username")
            await asyncio.sleep(2)
            if login_page:
                await page.fill_field_and_enter('#login_username', username)
                await asyncio.sleep(3)
                if remember_me:
                    await page.click('#login_rememberme')
                await page.fill_field_and_enter('#login_password', password)
                await asyncio.sleep(3)
                await page.fill_field_and_enter('#login_answer', security_question_answer)
            elif await page.check_for_element('section[data-test="freelancer-sidebar-profile"]'):
                if scrape_best:
                    first_link = True
                    new_jobs_num = 0
                    best_match_button = await page.get_element('button[data-test="tab-best-matches"]')
                    if best_match_button:
                        await page.click(best_match_button)
                        await asyncio.sleep(1)
                        job_tiles = await page.get_all_elements('section[data-ev-sublocation="job_feed_tile"]')
                        for job_posting in job_tiles:
                            job_posted_time_element = await job_posting.query_selector('span[data-test="posted-on"]')
                            job_posted_time = await page.get_text_content(job_posted_time_element) if job_posted_time_element else "N/A"
                            print(f"Job posted time: {job_posted_time}")
                            link_div = await job_posting.query_selector('a[data-ev-label="link"]')
                            link = await link_div.get_attribute('href')
                            if not link:
                                payload = {"status": "Failed", "message":"Problem extracting link ... \nMaybe the website structure has changed"}
                                print(payload)
                                await client.post(url = send_job_updates_webhook_url, json = payload)
                                print("link_extraction_failed")
                                return 
                            link = upwork_url + link
                            if first_link:
                                latest_best_link = link
                                first_link = False
                            if link == state["latest_urls"].get("Best Match",None) or \
                                ("minutes" not in job_posted_time.lower().split(sep=" ") and "minute" not in job_posted_time.lower().split(sep=" ")):
                                print(f"last_link in Best Match")
                                break
                            await page.click(link_div, wait_for='li[data-qa="client-location"] strong')
                            
                            status, job_details = await scrape_job(page=page)
                            
                            if status:
                                """Update db"""
                                job_update_status, msg = await add_job(job_url=link,job_description=job_details)
                                if not job_update_status and "duplicate key" in msg.get("message","").lower():
                                    print(f"Job already exists in db - {link}")
                                    await page.go_back()
                                    await asyncio.sleep(1)
                                    continue
                                elif not job_update_status:
                                    await client.post(url = send_job_updates_webhook_url, json = msg)
                                    print(f"db update error - {msg}")
                                    return
                                else:
                                    payload = {
                                        "status" : "Done",
                                        "category" : "Best Match",
                                        "url" : link,
                                        "job_details" : job_details
                                    }
                                    await client.post(url = send_job_updates_webhook_url, json = payload)
                                    new_jobs_num += 1
                                    print(f"job {new_jobs_num} sent.")
                            else:
                                job_details["url"] = link
                                await client.post(url = send_job_updates_webhook_url, json = job_details)
                                print(f"scraping failed - {job_details}")
                                
                            await page.go_back()
                            await asyncio.sleep(1)
                    state["latest_urls"]["Best Match"] = latest_best_link
                return True, "Already logged in.", new_jobs_num or None
            else:
                return False, "Login page could not be found."
        except Exception as e:
            print(f"Error during login: {e}")
            return False, f"Login attempt failed - {e}"
        finally:
            await page.goto(home_url)

@app.post("/generate_proposal")
async def generate_proposal_api(job_url:str):
    job_details = await get_job_by_url(job_url=job_url)
    if not job_details:
        return {"status" : "Failed", "message" : "Job details not found in database."}
    job_details = json.dumps(job_details)
    print(f"Job Details: {job_details}")
    proposal, proposal_model = await call_proposal_generator_agent(state["bidder_agent"], job_details)
    payload = {
        "status" : "Done",
        "job_url" : job_url,
        "proposal" : proposal
    }
    response = await add_proposal(job_url=job_url, proposal = proposal_model, applied=False)
    if response:
        return payload
    else:
        print(response)
        return response
    

async def apply_for_job(job_url: str):
    async with httpx.AsyncClient() as client:
        try:
            page = state["page"]
            job_proposal = await get_proposal_by_url(job_url=job_url)
            if not job_proposal:
                payload = {"status" : "Failed", "message" : "No proposal found for this job in database."}
                print(payload)
                await client.post(url = send_job_updates_webhook_url, json = payload)
                return
            login_status, message = await login_to_upwork(page=page, username="ali-maharuf", password="@neomaharuf124!", security_question_answer="Neoito")
            if not login_status:
                payload =  {"status" : "Failed", "message" : f"Login failed - {message}"}
                print(payload)
                await client.post(url = send_job_updates_webhook_url, json = payload)
            await page.goto(job_url, wait_for = 'button[data-cy="submit-proposal-button"]', captcha_selector=cloudfare_challenge_div_id, wait_until= "domcontentloaded", referer="https://www.upwork.com")
            await asyncio.sleep(2)
            
            await page.scroll_by(450)
            await page.click(selector = 'button[data-cy="submit-proposal-button"]', expect_navigation=True)
            await asyncio.sleep(3)
            cover_letter = job_proposal.cover_letter
            await page.copy_to_clipboard(cover_letter)
            await page.paste_from_clipboard(selector = 'textarea[aria-labelledby="cover_letter_label"]')
            
            questions_and_answers = question_answer_parser(job_proposal)
            
            q_a_divs = await page.get_all_elements(selector = 'div.fe-proposal-job-questions > div')
            for div in q_a_divs:
                question_label = await div.query_selector('label.label')
                question_in_page = await question_label.text_content()
                print(question_in_page.strip())
                print(questions_and_answers[question_in_page.strip()])
                text_area = await div.query_selector('textarea')
                await page.copy_to_clipboard(questions_and_answers[question_in_page.strip()])
                await page.paste_from_clipboard(selector = text_area)
            input("enter to finish : ")
            payload = {"status" : "Success", "message" : f"Application completed for job - {job_url}"}
            print(payload)
            await client.post(url = send_job_updates_webhook_url, json = payload)
        except Exception as e:
            payload = {"status" : "Failed", "message" : f"Error occured during application - {e}"}
            print(payload)
            await client.post(url = send_job_updates_webhook_url, json = payload)
        finally:
            await page.goto(home_url)
        
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
                    status, message = await check_for_jobs()
                    print(message)
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