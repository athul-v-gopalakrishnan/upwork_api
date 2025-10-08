from utils.job_counter import JobCounter
from utils.constants import send_job_updates_webhook_url
from utils.session import Session

from nyx.page import NyxPage

import httpx
import asyncio

class ScraperSession(Session):
    def __init__(
            self, page:NyxPage, 
            links_to_visit:dict[str, str], 
            username:str,
            password:str, 
            security_answer:str = None
        ):
        super().__init__(page, username, password, security_answer)
        self.links_to_visit = links_to_visit
        self.job_counter = JobCounter()
        
    async def run(self):
        await self.setup_client()
        for category, url in self.links_to_visit.items():
            await self.scrape_job_page(category, url)
                
    async def scrape_job_page(self, category:str, url:str):
        pass
    
    async def scrape_login_page(self):
        pass
    
    async def send_job_update(self, job_data:dict):
        pass