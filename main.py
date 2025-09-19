from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json

from nyx.browser import NyxBrowser

from upwork_agent.bidder_agent import build_bidder_agent,call_proposal_generator_agent
from vault.db_config import DB_CONNECTION_STRING

from langgraph.checkpoint.postgres import PostgresSaver

state = {}

# async def start_browser():
#     browser = NyxBrowser()
#     await browser.start()
#     state['browser'] = browser

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    browser = NyxBrowser()
    await browser.start()
    state['browser'] = browser
    print("Browser started")
    page = await state.get("browser").new_page() 
    state["page"] = page
    print("Page created")
    yield
    # Shutdown code
    await browser.shutdown()

state["bidder_agent"] = build_bidder_agent()
print("Bidder agent created")
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
        page = state["page"] 
        await page.goto(job_url,captcha_selector="#wNUym6",wait_until= "domcontentloaded",referer="https://www.upwork.com")
        await asyncio.sleep(2)  # Wait for a few seconds to ensure the page loads
        
        client_location = await page.get_text_content('li[data-qa="client-location"] strong')
        job_details["client_location"] = client_location.strip() if client_location else "N/A"
        
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
            for q_element in question_elements:
                question_text = await page.get_text_content(q_element)
                questions.append(str(question_number) + ". " + question_text.strip() + "\n")
            job_details["questions"] = " ".join(questions)
        else:
            job_details["questions"] = "N/A"
        
        job_details["status"] = "Done"
        print(job_details)
        return job_details
    except Exception as e:
        print(e)
        return {"status": "Failed to visit job page", "error": str(e)}

@app.get("/login_to_upwork")
async def login_to_upwork(username: str, password: str,security_question_answer: str = None, remember_me: bool = True):
    try:
        page = state["page"]
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
    return {"status": "Login attempt finished"}

@app.post("/generate_proposal")
async def generate_proposal_api(job_description: str, tech:str = None, questions: str = None):
    job_details = {
        "summary": job_description,
        "technologies": tech if tech else "N/A",
        "questions": questions if questions else "N/A"
    }
    job_details = json.dumps(job_details)
    print(f"Job Details: {job_details}")
    proposal = call_proposal_generator_agent(state["bidder_agent"], job_details)
    return proposal

# @app.post("/apply_for_job")
# async def apply_for_job()
    

if __name__ == "__main__":
    asyncio.run(login_to_upwork("vggvn8n@gmail.com", "upwork@automation"))