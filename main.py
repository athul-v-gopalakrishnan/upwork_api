from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from nyx.browser import NyxBrowser

state = {}

async def start_browser():
    browser = NyxBrowser()
    await browser.start()
    state['browser'] = browser

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
        job_details = {}
        page = state["page"] 
        await page.goto(job_url,captcha_selector="#LsMgo8",wait_until= "domcontentloaded",referer="https://www.upwork.com")
        await asyncio.sleep(2)  # Wait for a few seconds to ensure the page loads
        
        client_location = await page.get_text_content('li[data-qa="client-location"] strong')
        job_details["client_location"] = client_location
        
        hire_rate = await page.get_text_content('li[data-qa="client-job-posting-stats"] div')
        job_details["hire_rate"] = hire_rate
        
        total_spent = await page.get_text_content('li strong[data-qa="client-spend"] span')
        job_details["total_spent"] = total_spent
        
        member_since = await page.get_text_content('li[data-qa="client-contract-date"] small')
        job_details["member_since"] = member_since
        
        summary_element = await page.get_all_elements('div[data-test="Description"] *')
        summary = ""
        for element in summary_element:
            summary += await page.get_text_content(element)
        job_details["summary"] = summary.strip()
        
        duration_elements = await page.get_all_elements('div[data-cy*="duration"] + strong span')
        duration = await page.get_text_content(duration_elements[0]) if duration_elements else "N/A"
        job_details["duration"] = duration
        
        rate_divs = await page.get_all_elements('div[data-cy="clock-timelog"] + div strong')
        rates = []
        for div in rate_divs:
            rates.append(await page.get_text_content(div))
        hourly_rate = "-".join(rates)
        job_details["hourly_rate"] = hourly_rate
        
        skill_elements = await page.get_all_elements('div.skills-list span span a div div')
        skills = []
        for element in skill_elements:
            skills.append(await page.get_text_content(element))
        job_details["skills"] = ", ".join(skills)
        
        return job_details
    except Exception as e:
        print(e)
        return {"status": "Failed to visit job page", "error": str(e)}

@app.get("/login_to_upwork")
async def login_to_upwork(username: str, password: str,security_question_answer: str = None, remember_me: bool = True):
    try:
        page = state["page"]
        await page.goto("https://www.upwork.com/ab/account-security/login",captcha_selector="#LsMgo8",wait_until= "domcontentloaded",referer="https://www.upwork.com") 
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

if __name__ == "__main__":
    asyncio.run(login_to_upwork("vggvn8n@gmail.com", "upwork@automation"))