from utils.constants import upwork_login_url, cloudfare_challenge_div_id, upwork_url, home_url

from nyx.page import NyxPage

from httpx import AsyncClient
from pydantic import BaseModel
import asyncio

class Session:
    def __init__(self, page:NyxPage, username: str, password: str, security_answer: str = None, status_endpoint:str = None, payload_endpoint:str = None, payload:BaseModel = None):
        self.username = username
        self.password = password
        self.security_answer = security_answer
        self.client = None
        self.page = page
        self.payload:BaseModel = payload
        self.status_endpoint = status_endpoint
        self.payload_endpoint = payload_endpoint
        self.status = {}
    
    async def setup_client(self):
        try:
            self.client = AsyncClient()
            return True 
        except Exception as e:
            self.update_status("Failed", f"Error setting up HTTP client: {e}")
            self.send_status()
            self.print_status()
            return False
        
    async def close_client(self):
        if self.client:
            await self.client.aclose()
            
    def update_status(self, status:str, message:str):
        self.status["status"] = status
        self.status["message"] = message
                    
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
                self.update_status("Success", "Already logged in")
                return True
            else:
                self.update_status("Failed", "Login page not found")
                await self.send_status()
                self.print_status()
                return False
        except Exception as e:
            self.update_status("Failed", f"Error during login: {e}")
            await self.send_status()
            self.print_status()
            await self.page.goto(home_url)
            return False
        finally:
            if not to_scrape:
                await self.page.goto(home_url)
                
    async def send_status(self):
        if not self.status_endpoint:
            self.status["status"] = "Failed"
            self.status["message"] = "Set the status_endpoint parameter in Session initialisation."
            return False
        if not self.client:
            await self.setup_client()
        try:
            await self.client.post(self.status_endpoint, json=self.status)
            return True
        except Exception as e:
            self.status["status"] = "Failed"
            self.status["message"] = f"Error sending status: {e}"
            return False
        
    def print_status(self):
        print(f"{self.status["status"]} -- {self.status["message"]}")
        
    async def send_payload(self):
        if not self.payload_endpoint:
            self.status["status"] = "Failed"
            self.status["message"] = "Set the payload_endpoint parameter in Session initialisation."
            return False
        if not self.client:
            await self.setup_client()
        try:
            await self.client.post(self.payload_endpoint, json=self.payload.model_dump_json())
            return True
        except Exception as e:
            self.status["status"] = "Failed"
            self.status["message"] = f"Error sending payload: {e}"
            return False

        