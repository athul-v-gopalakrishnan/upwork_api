from utils.session import Session
from utils.constants import upwork_login_url, cloudfare_challenge_div_id, upwork_url, home_url
from utils.models import Proposal

from db_utils.access_db import get_proposal_by_url, update_proposal_by_url

from typing import Literal, Optional
import asyncio
import re 

from nyx.page import NyxPage

class ApplicationSession(Session):
    def __init__(self,
                 page:NyxPage, 
                 job_url:str,
                 username:str, 
                 password:str,
                 human:str,
                 security_answer:str = None, 
                 status_endpoint:str = None,
                 ):
        super().__init__(page, username, password, security_answer, status_endpoint)
        self.job_url = job_url
        self.human = human
        self.applied = False
        self.proposal:Optional[Proposal] = None
        self.proposal_type:Optional[Literal["Hourly", "Fixed Price"]] = None
        
    async def run(self):
        proposal_fetch_status = await self.get_proposal()
        if not proposal_fetch_status:
            await self.send_status()
            self.print_status()
            return False
        login_status = await self.login(upwork_login_url)
        if not login_status:
            await self.send_status()
            self.print_status()
            return False
        reach_bidding_page_status = await self.reach_bidding_page()
        if not reach_bidding_page_status:
            await self.send_status()
            self.print_status()
            return False
        apply_status = await self.apply_for_job()
        if not apply_status:
            await self.send_status()
            self.print_status()
            return False
        update_proposal_status = await self.update_proposal_status()
        if not update_proposal_status:
            await self.send_status()
            self.print_status()
            return False
        self.update_status("Success", "Application process completed successfully")
        await self.send_status()
        self.print_status()
        return True
        
    async def reach_bidding_page(self):
        try:
            await self.page.goto(self.job_url, wait_for = 'button[data-cy="submit-proposal-button"]', captcha_selector=cloudfare_challenge_div_id, wait_until= "domcontentloaded", referer="https://www.upwork.com")
            await self.page.click(selector = 'button[data-cy="submit-proposal-button"]', expect_navigation=True)
            await asyncio.sleep(1)
            return True
        except Exception as e:
            self.update_status("Failed", f"Error reaching job page: {e}")
            await self.send_status()
            self.print_status()
            return False
    
    async def get_proposal(self):
        try:
            existing_proposal = await get_proposal_by_url(self.job_url)
            self.proposal = existing_proposal
            if existing_proposal:
                self.proposal_type = existing_proposal.get("job_type")
            else:
                self.update_status("Failed", "No existing proposal found for the job URL")
                await self.send_status()
                self.print_status()
                return False
            return True
        except Exception as e:
            self.update_status("Failed", f"Error retrieving proposal: {e}")
            await self.send_status()
            self.print_status()
            return False
        
    async def update_proposal_status(self):
        if not self.proposal:
            self.update_status("Failed", "No proposal to update")
            await self.send_status()
            self.print_status()
            return False
        try:
            updates = {
                "applied": self.applied, 
                "approved_by": self.human
                }
            update_status, msg = await update_proposal_by_url(self.job_url, updates)
            if not update_status:
                self.update_status("Failed", f"Database update error - {msg}")
                await self.send_status()
                self.print_status()
                return False
            self.print_status()
            return True
        except Exception as e:
            self.update_status("Failed", f"Error updating proposal status: {e}")
            await self.send_status()
            self.print_status()
            return False
        
    async def apply_for_job(self):
        if not self.proposal:
            self.update_status("Failed", "No proposal to apply with")
            await self.send_status()
            self.print_status()
            return False
        try:
            await self.page.goto(self.job_url, wait_for = 'button[data-cy="submit-proposal-button"]', captcha_selector=cloudfare_challenge_div_id, wait_until= "domcontentloaded", referer="https://www.upwork.com")
            await asyncio.sleep(2)
            
            await self.page.scroll_by(450)
            await self.page.click(selector = 'button[data-cy="submit-proposal-button"]', expect_navigation=True, wait_for=None)
            await asyncio.sleep(3)
            if self.proposal_type == "Fixed Price":
                return True
            cover_letter = self.proposal.cover_letter
            await self.page.copy_to_clipboard(cover_letter)
            await self.page.paste_from_clipboard(selector = 'textarea[aria-labelledby="cover_letter_label"]')
            
            questions_and_answers = self.question_answer_parser()
            if questions_and_answers:
                q_a_divs = await self.page.get_all_elements(selector = 'div.fe-proposal-job-questions > div')
                for div in q_a_divs:
                    question_label = await div.query_selector('label.label')
                    question_in_page = await question_label.text_content()
                    print(question_in_page.strip())
                    print(questions_and_answers[question_in_page.strip()])
                    text_area = await div.query_selector('textarea')
                    await self.page.copy_to_clipboard(questions_and_answers[question_in_page.strip()])
                    await self.page.paste_from_clipboard(selector = text_area)
            input("enter to finish : ")
            self.applied = True 
            self.print_status()
            return True
        except Exception as e:
            self.update_status("Failed", f"Error applying for job: {e}")
            await self.send_status()
            self.print_status()
            return False
        
    def question_answer_parser(self):
        q_a_dict = {}
        if len(self.proposal.questions_and_answers) == 0:
            return None
        for question_and_answer in self.proposal.questions_and_answers:
            question = re.sub(r"^\d+\.\s*", "", question_and_answer.question.strip())
            answer = question_and_answer.answer.strip()
            q_a_dict[question] = answer
        return q_a_dict
        
    
    