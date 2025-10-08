from utils.constants import upwork_login_url, cloudfare_challenge_div_id, upwork_url, home_url

from nyx.page import NyxPage

from httpx import AsyncClient
import asyncio

class Session:
    def __init__(self, page:NyxPage, username: str, password: str, security_answer: str = None):
        self.username = username
        self.password = password
        self.security_answer = security_answer
        self.client = None
        self.page = page
    
    async def setup_client(self):
        self.client = AsyncClient()
        
    async def close_client(self):
        if self.client:
            await self.client.aclose()
                    
    async def login(self, remember_me:bool = True, to_scrape:bool = False):
        try:
            await self.page.goto(upwork_login_url,captcha_selector=cloudfare_challenge_div_id,wait_until= "domcontentloaded",referer=upwork_url) 
            login_page = await self.page.check_for_element("#login_username")
            await asyncio.sleep(2)
            if login_page:
                await self.page.fill_field_and_enter('#login_username', self.username)
                await asyncio.sleep(3)
                if remember_me:
                    await self.page.click('#login_rememberme')
                await self.page.fill_field_and_enter('#login_password', self.password)
                await asyncio.sleep(3)
                await self.page.fill_field_and_enter('#login_answer', self.security_question_answer)
            elif await self.page.check_for_element('section[data-test="freelancer-sidebar-profile"]'):
                return True, "Already logged in"
            else:
                return False, "Login page not found"
        except Exception as e:
            print(f"Error during login: {e}")
            return False, f"Login attempt failed - {e}"
        finally:
            if not to_scrape:
                await self.page.goto(home_url)
                
    async def send_status(self, status:str):
        pass