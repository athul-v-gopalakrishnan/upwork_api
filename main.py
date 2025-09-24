from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json

from nyx.browser import NyxBrowser

from upwork_agent.bidder_agent import build_bidder_agent,call_proposal_generator_agent, Proposal
from vault.db_config import MEMORYDB_CONNECTION_STRING, dbname, username, password
from db_utils.access_db import add_proposal, create_proposals_table, get_proposal_by_url

from langgraph.checkpoint.postgres import PostgresSaver

state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    browser = NyxBrowser()
    await browser.start()
    state['browser'] = browser
    print("Browser started")
    page_pool = await state.get("browser").create_page_pool(page_pool_name = "upwork_pool", page_pool_size = 10)
    state["page_pool"] = page_pool
    print("Page pool created")
    cm = PostgresSaver.from_conn_string(MEMORYDB_CONNECTION_STRING)
    state["checkpointer"] = cm.__enter__()
    state["checkpointer"].setup()
    state["bidder_agent"] = build_bidder_agent(state["checkpointer"])
    print("Bidder agent created")
    state["application_underway"] = False
    await create_proposals_table()
    print("proposals table created.")
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

@app.get("/visit_job")
async def visit_job(job_url: str):
    try:
        if state["last_url"] == job_url:
            return {"status": "No new jobs to visit."}
        state["last_url"] = job_url
        job_details = {}
        page = await state["page_pool"].get_idle_page()
        await page.goto(job_url,captcha_selector="#AJXH4",wait_until= "domcontentloaded",referer="https://www.upwork.com")
        await asyncio.sleep(2)  # Wait for a few seconds to ensure the page loads
        
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
        
        job_details["status"] = "Done"
        print(job_details)
        return job_details
    except Exception as e:
        print(e)
        return {"status": "Failed to visit job page", "error": str(e)}
    finally:
        await state["page_pool"].release(page)

@app.get("/login_to_upwork")
async def login_to_upwork(username: str, password: str,security_question_answer: str = None, remember_me: bool = True):
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
        else:
            return {"status": "Already logged in or login page not found."} 
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
            input("enter to fnish : ")
        else:
            return {"status" : "Please wait for the current application process to finish to apply for more jobs."}
    except Exception as e:
        print(f"Excception occured : {e}")
    finally:
        await state["page_pool"].release(page)
        state["application_underway"] = False
    

if __name__ == "__main__":
    asyncio.run(login_to_upwork("https://www.upwork.com/jobs/~021970351209921008305?link=new_job&frkscc=HilbNikXAzRX", "upwork@automation"))