from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
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
from db_utils.access_db import add_proposal, create_proposals_table, get_proposal_by_url, create_jobs_table, get_job_by_url, add_job
from utils.constants import send_job_updates_webhook_url

from langgraph.checkpoint.postgres import PostgresSaver

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
        "Business Intelligence" : None
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    browser = NyxBrowser()
    await browser.start()
    state['browser'] = browser
    print("Browser started")
    state["filter_urls"] = {
        "Frontend" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&q=angular%20OR%20React%20OR%20Javascript%20OR%20Typescript&sort=recency&t=0,1",
        "Backend" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=2,3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&q=NodeJS%20OR%20Golang%20OR%20Python%20OR%20Database%20OR%20MongoDB%20OR%20SQL%20OR%20postgresql%20OR%20API%20Integration&sort=recency&t=0,1",
        "Fullstack" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=MEAN%20OR%20MERN%20OR%20Fullstack%20OR%20MongoDB&sort=recency&t=0,1",
        "Mobile" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=%22React%20Native%22%20OR%20Flutter%20OR%20PWA%20OR%20%22%20Progressive%20Web%20App%22&sort=recency&t=0,1",
        "AI/ML" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=natural%20language%20processing%20or%20nlp%20or%20tensorflow%20or%20opencv%20or%20mlops%20or%20ml%20or%20machine%20learning%20or%20chatbot&sort=recency&t=0,1",
        "GenAI" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=artificial%20intelligence%20or%20ai%20agent%20or%20ai%20or%20agenti%20ai%20or%20rag%20or%20llm%20or%20large%20language%20model%20or%20data%20science%20or%20open%20ai&sort=recency&t=0,1",
        "Devops" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=Docker%20OR%20Pineline%20OR%20CI%2FCD%20OR%20AWS%20OR%20GCP%20OR%20Azure%20OR%20Monitoring%20OR%20Prometheus%20OR%20Grafana%20OR%20Kubernetes&sort=recency&t=0,1",
        "IOT" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=IoT%20OR%20Internet%20of%20Things&sort=recency&t=0,1",
        "Low code/No code" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=2,3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=Bubble%20OR%20Webflow&sort=recency&t=0,1",
        "Non Tech" : "https://www.upwork.com/nx/search/jobs/?amount=5000-&contractor_tier=2,3&duration_v3=month,semester,ongoing&hourly_rate=15-&location=Americas,Europe,Oceania&per_page=50&q=web%20OR%20development%20OR%20software%20OR%20Mobile%20OR%20MVP%20OR%20SAAS%20OR%20Startup%20OR%20AI&sort=recency&t=0,1",
        "Data Engineering" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=power%20bi%20or%20data%20engineering%20or%20snowflake%20or%20dashboard&sort=recency&t=0,1",
        "Business Intelligence" : "https://www.upwork.com/nx/search/jobs/?amount=2000-&contractor_tier=2,3&duration_v3=month,semester,ongoing&hourly_rate=15-&payment_verified=1&q=data%20analysis%20or%20data%20analyst%20or%20quicksight%20or%20etl%20or%20elt%20or%20dax%20or%20data%20lakehouse%20or%20sql%20or%20bi%20or%20ai%20byte%20or%20business%20intelligence&sort=recency&t=0,1"
    }
    state["latest_urls"] = latest_urls
    page_pool = await state.get("browser").create_page_pool(page_pool_name = "upwork_pool", page_pool_size = 10)
    state["page_pool"] = page_pool
    print("Page pool created")
    cm = PostgresSaver.from_conn_string(MEMORYDB_CONNECTION_STRING)
    state["checkpointer"] = cm.__enter__()
    state["checkpointer"].setup()
    state["bidder_agent"] = build_bidder_agent(state["checkpointer"])
    print("Bidder agent created")
    state["application_underway"] = False
    proposal_table_status, msg = await create_proposals_table()
    print(proposal_table_status, msg)
    job_table_status, msg = await create_jobs_table()
    print(job_table_status, msg)
    yield
    # Shutdown code
    cm.__exit__(None, None, None)
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

@app.get("/check_for_jobs")
async def check_for_jobs():
    try:
        page = await state["page_pool"].get_idle_page() 
        upwork_url = "https://www.upwork.com"
        session_latest_links = {}
        new_jobs_num = 0
        async with httpx.AsyncClient() as client:
            for category, url in state["filter_urls"].items():
                first_link = True
                await page.goto(url,captcha_selector="#AJXH4",wait_until= "domcontentloaded",referer="https://www.upwork.com/")
                await asyncio.sleep(2)
                job_postings = await page.get_all_elements(selector='article[data-test="JobTile"]')
                for job_posting in job_postings:
                    link_div = await job_posting.query_selector('a[data-test="job-tile-title-link UpLink"]')
                    link = await link_div.text_content()
                    if not link:
                        payload = {"status":"Problem extracting link ... \nMaybe the website structure has changed"}
                        print(payload)
                        await client.post(url = send_job_updates_webhook_url, json = payload)
                        print("link_extraction_failed")
                        return 
                    link = upwork_url + link
                    if first_link:
                        session_latest_links[category] = link
                        first_link = False
                    if link == state["latest_urls"].get(category,None):
                        print(f"last_link in {category}")
                        break
                    await page.click(job_posting)
                    await asyncio.sleep(2)
                    
                    status, job_details = await scrape_job(page=page)
                    if status:
                        """Update db"""
                        job_update_status, msg = await add_job(job_url=link,job_description=job_details)
                        if not job_update_status:
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
                        await client.post(url = send_job_updates_webhook_url, json = job_details)
                        print(f"scraping failed - {job_details}")
                        return
                    await page.go_back()
                    await asyncio.sleep(1)
                    if new_jobs_num == 3:
                        print("working aan hehe")
                        return
                
        
        state["latest_urls"] = session_latest_links 
        with open(latest_urls_path, 'wb') as f:
            pickle.dump(session_latest_links, f)   
        return {"status" : f"Successfully checked for new jobs. {new_jobs_num} jobs found."}   
    except Exception as e:
        return {"status" : f"Check failed. Error - {e}"}
    finally:
        await state["page_pool"].release(page)
    

async def scrape_job(page:NyxPage):
    try:
        job_details = {}
        
        client_location = await page.get_text_content('li[data-qa="client-location"] strong')
        job_details["client_location"] = client_location.strip() if client_location else "N/A"
        
        if job_details["client_location"] == "N/A":
            job_details["status"] = "Page loaded but failed to extract job details, possibility of a private job posting."
            return job_details
        
        hire_rate = await page.get_text_content('li[data-qa="client-job-posting-stats"] div')
        job_details["hire_rate"] = hire_rate.strip() if hire_rate else "N/A"
        
        total_spent = await page.get_text_content('li strong[data-qa="client-spend"] span')
        job_details["total_spent"] = total_spent.strip() if hire_rate else "N/A"
        
        member_since = await page.get_text_content('li[data-qa="client-contract-date"] small')
        job_details["member_since"] = member_since.strip() if hire_rate else "N/A"
        
        summary_element = await page.get_all_elements('div[data-test="Description"] p')
        summary = ""
        for element in summary_element:
            summary_chunk = await page.get_text_content(element)
            summary += summary_chunk.strip() + " "
        job_details["summary"] = summary.strip()
        
        duration_elements = await page.get_all_elements('div[data-cy*="duration"] + strong span')
        duration = await page.get_text_content(duration_elements[0]) if duration_elements else "N/A"
        job_details["duration"] = duration.strip()
        
        price_div = await page.get_element('div[data-cy="fixed_price"] + div strong')
        if price_div:
            price = await page.get_text_content(price_div).strip()
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
        
        print(f"Checking for questions section...")
        print(await page.check_for_element('section[data-test="Questions"]'))
        
        if await page.check_for_element('section[data-test="Questions"]'):
            question_number = 1
            questions = []
            question_elements = await page.get_all_elements('section[data-test="Questions"] ol li')
            print(question_elements)
            for q_element in question_elements:
                print(q_element)
                question_text = await page.get_text_content(q_element)
                questions.append(str(question_number) + ". " + question_text.strip() + "\n")
                question_number+=1
            job_details["questions"] = " ".join(questions)
            print(job_details["questions"])
        else:
            job_details["questions"] = "N/A"
        return True, job_details
    except Exception as e:
        print(e)
        await state["page_pool"].release(page)
        return False, {"status": "Failed to visit job page", "error": str(e)}

        

@app.get("/login_to_upwork")
async def login_to_upwork(username: str, password: str, security_question_answer: str = None, remember_me: bool = True):
    try: 
        page = await state["page_pool"].get_idle_page()
        await page.goto("https://www.upwork.com/ab/account-security/login",captcha_selector="#wNUym6",wait_until= "domcontentloaded",referer="https://www.upwork.com") 
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
            return {"status": "Already logged in."} 
        else:
            return {"status" : "Login page could not be found."}
    except Exception as e:
        print(f"Error during login: {e}")
        return {"status": "Login attempt failed", "error": str(e)}
    finally:
        await state["page_pool"].release(page)
        return {"status": "Login attempt finished"}

@app.post("/generate_proposal")
async def generate_proposal_api(job_url:str, job_description: str, tech:str = None, questions: str = None):
    job_details = {
        "summary": job_description,
        "technologies": tech if tech else "N/A",
        "questions": questions if questions else "N/A"
    }
    job_details = json.dumps(job_details)
    print(f"Job Details: {job_details}")
    proposal, proposal_model = call_proposal_generator_agent(state["bidder_agent"], job_details)
    response = await add_proposal(job_url=job_url, proposal = proposal_model, applied=False)
    if response:
        return proposal
    else:
        print(response)
        return response
    

@app.post("/apply_for_job")
async def apply_for_job(job_url: str):
    try:
        if not state["application_underway"]:
            state["application_underway"] = True
            job_proposal = await get_proposal_by_url(job_url=job_url)
            page = await state["page_pool"].get_idle_page()
            await page.goto(job_url,captcha_selector="#AJXH4", wait_until= "domcontentloaded", referer="https://www.upwork.com")
            await asyncio.sleep(2)
            
            await page.scroll_by(450)
            await page.click(selector = 'button[data-cy="submit-proposal-button"]')
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
        else:
            return {"status" : "Please wait for the current application process to finish to apply for more jobs."}
    except Exception as e:
        print(f"Excception occured : {e}")
    finally:
        await state["page_pool"].release(page)
        state["application_underway"] = False
        
def question_answer_parser(proposal:Proposal):
    q_a_dict = {}
    for question_and_answer in proposal.questions_and_answers:
        question = re.sub(r"^\d+\.\s*", "", question_and_answer.question.strip())
        answer = question_and_answer.answer.strip()
        q_a_dict[question] = answer
    return q_a_dict

if __name__ == "__main__":
    hehe = asyncio.run(question_answer_parser("https://www.upwork.com/jobs/~021970706874169818481?link=new_job&frkscc=NYf13dCiTalJ"))
    print(hehe)