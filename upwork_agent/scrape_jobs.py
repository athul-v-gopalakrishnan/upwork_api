from utils.job_counter import JobCounter
from utils.constants import send_job_updates_webhook_url,upwork_url, home_url\
    , cloudfare_challenge_div_id, send_job_updates_webhook_url_test
from utils.session import Session
from utils.models import FinalJobPayload
from utils.job_filter import JobFilter
from db_utils.access_db import add_job


from nyx.page import NyxPage

import asyncio
import traceback
import pickle

class ScraperSession(Session):
    def __init__(
            self, page:NyxPage, 
            links_to_visit:dict[str, str], 
            last_links:dict[str, str],
            username:str,
            password:str, 
            security_answer:str = None,
            status_endpoint:str = send_job_updates_webhook_url,
            job_filter = JobFilter()
        ):
        super().__init__(page = page, username = username, password=password, security_answer=security_answer, status_endpoint=status_endpoint, payload_endpoint=status_endpoint, payload=FinalJobPayload())
        self.links_to_visit = links_to_visit
        self.job_counter = JobCounter()
        self.latest_links = last_links
        self.session_latest_links = {}
        self.job_details = {}
        self.job_filter = job_filter
        
    async def run(self):
        try:
            client_setup_success = await self.setup_client()
            if not client_setup_success:
                return False
        except Exception as e:
            print(f"Error setting up client: {e}")
        try:
            login_success = await self.login(to_scrape=True)
            if not login_success:
                return False
            login_page_scraper_success = await self.scrape_login_page()
            if not login_page_scraper_success:
                return False
            for category, url in self.links_to_visit.items():
                print(f"Visiting category: {category} - {url}")
                job_page_visit_status = await self.visit_job_page(url)
                if not job_page_visit_status:
                    continue
                job_page_scrape_status = await self.scrape_listed_jobs(category)
                if not job_page_scrape_status:
                    return False
                await asyncio.sleep(2)
            self.update_status("Done", f"Scraping session completed. {self.job_counter.get_count()} new jobs found.")
            await self.send_status()
            self.print_status()
            await self.close_client()
            await self.page.goto(home_url)
            return True
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.update_status("Failed", f"Error in scraping session: {e}")
            await self.send_status()
            self.print_status()
            await self.close_client()
            await self.page.goto(home_url)
            return False
        finally:
            with open("latest_links.pkl", "wb") as f:
                pickle.dump(self.get_latest_links(), f)
                
                
    async def scrape_job_page(self):
        try:
            self.job_details = {}
            
            client_location = await self.page.get_text_content('li[data-qa="client-location"] strong')
            self.job_details["client_location"] = client_location.strip() if client_location else "N/A"
            
            if self.job_details["client_location"] == "N/A":
                self.status["status"] = "Failed"
                self.status["message"] = "Page loaded but failed to extract job details, possibility of a private job posting."
                return False
            
            hire_rate = await self.page.get_text_content('li[data-qa="client-job-posting-stats"] div')
            self.job_details["hire_rate"] = hire_rate.strip() if hire_rate else "N/A"
            
            total_spent = await self.page.get_text_content('li strong[data-qa="client-spend"] span span')
            self.job_details["total_spent"] = total_spent.strip() if total_spent else "N/A"
            
            member_since = await self.page.get_text_content('li[data-qa="client-contract-date"] small')
            self.job_details["member_since"] = member_since.strip() if member_since else "N/A"
            
            payment_verified = await self.page.check_for_element('div.payment-verified')
            print(f"Payment verified: {payment_verified}")
            self.job_details["payment_verified"] = payment_verified
            
            summary_element = await self.page.get_all_elements('div[data-test="Description"] p')
            summary = ""
            for element in summary_element:
                summary_chunk = await self.page.get_text_content(element)
                summary += summary_chunk.strip() + " "
            self.job_details["summary"] = summary.strip()
            
            duration_type_elements = await self.page.get_all_elements('div[data-cy*="duration"]')
            duration_elements = await self.page.get_all_elements('div[data-cy*="duration"] + strong > span')
            duration_type = await duration_type_elements[0].get_attribute('data-cy') if duration_type_elements else None
            duration = await self.page.get_text_content(duration_elements[0]) if duration_elements else "N/A"
            self.job_details["duration_type"] = duration_type.strip() if duration_type else "N/A"
            self.job_details["duration"] = duration.strip()
            
            price_div = await self.page.get_element('div[data-cy="fixed-price"] + div strong')
            if price_div:
                price = await self.page.get_text_content(price_div)
                self.job_details["hourly_rate"] = price.strip() if price else "N/A"
                self.job_details["job_type"] = "Fixed Price"
            else:        
                rate_divs = await self.page.get_all_elements('div[data-cy="clock-timelog"] + div strong')
                rates = []
                for div in rate_divs:
                    rate = await self.page.get_text_content(div)
                    rates.append(rate.strip())
                hourly_rate = "-".join(rates)
                self.job_details["hourly_rate"] = hourly_rate.strip() if hourly_rate else "N/A"
                self.job_details["job_type"] = "Hourly"
            
            skill_elements = await self.page.get_all_elements('div.skills-list span span a div div')
            skills = []
            for element in skill_elements:
                skill = await self.page.get_text_content(element)
                skills.append(skill.strip() + "\n")
            self.job_details["skills"] = ", ".join(skills)
            
            qualified = True
            if await self.page.check_for_element('ul.qualification-items'):
                qualification_elements = await self.page.get_all_elements('ul.qualification-items span.icons div')
                for element in qualification_elements:
                    qualification_status = await self.page.get_attribute(element, 'title')
                    if qualification_status == "You do not meet this qualification":
                        qualified = False
                        break
                    
            self.job_details["qualified"] = qualified
            
            if await self.page.check_for_element('section[data-test="Questions"]'):
                question_number = 1
                questions = []
                question_elements = await self.page.get_all_elements('section[data-test="Questions"] ol li')
                for q_element in question_elements:
                    question_text = await self.page.get_text_content(q_element)
                    questions.append(str(question_number) + ". " + question_text.strip() + "\n")
                    question_number+=1
                self.job_details["questions"] = " ".join(questions)
                print(self.job_details["questions"])
            else:
                self.job_details["questions"] = "N/A"
            return True
        except Exception as e:
            print(e)
            traceback.print_exc()
            await self.page.goto(home_url)
            self.update_status("Failed", f"Error scraping job page: {e}")
            await self.send_status()
            self.print_status()
            return False
        
    async def visit_job_page(self, link:str):
        try:
            await self.page.goto(link,wait_for = 'div[data-test="UpCInput"]', captcha_selector=cloudfare_challenge_div_id,wait_until= "domcontentloaded",referer=upwork_url)
        except Exception as e:
            self.update_status("Failed", f"Error visiting job page: {e}")
            await self.send_status()
            self.print_status()
            await self.page.goto(home_url)
            return False
        return True
    
    async def scrape_listed_jobs(self, category:str = "category1"):
        first_link = True
        job_postings = await self.page.get_all_elements(selector='article[data-test="JobTile"]')
        for job_posting in job_postings:
            try:
                job_posted_time_elements = await job_posting.query_selector_all('small[data-test="job-pubilshed-date"] span')
            except Exception as e:
                print(f"Error getting job posted time elements: {e}")
                input("Press Enter to  continue...")
                continue
            job_posted_time = ""
            for element in job_posted_time_elements:
                job_posted_time += await self.page.get_text_content(element) + " "
            job_posted_time = job_posted_time.strip()
            print(f"Job posted time: {job_posted_time}")
            link_div = await job_posting.query_selector('a[data-test="job-tile-title-link UpLink"]')
            link = await link_div.get_attribute('href')
            if not link:
                self.update_status("Failed", "Problem extracting link ... \nMaybe the website structure has changed")
                await self.send_status()
                self.print_status()
                return False
            link = upwork_url + link
            if first_link:
                self.session_latest_links[category] = link
                first_link = False
                
            is_recent_link = any(x in job_posted_time.lower() for x in ("minute", "minutes", "second", "seconds"))
            if link == self.latest_links.get(category,None) or not is_recent_link:
                print(f"last_link in {category}")
                break
            await self.page.click(link_div, wait_for='li[data-qa="client-location"] strong')
            
            scrape_success = await self.scrape_job_page()
            post_processing_success = await self.post_scraping_tasks(scrape_success, link, category)
            if not post_processing_success:
                return False
            await asyncio.sleep(2)
            await self.page.go_back()
            await asyncio.sleep(2)
        return True
    
    async def post_scraping_tasks(self, scrape_success:bool, link:str, category:str):
        if not scrape_success:
            await self.send_status()
            self.print_status()
            return False
        if not self.job_filter.is_job_allowed(self.job_details):
            print("Job filtered out based on criteria.")
            return True
        job_update_status, msg = await add_job(job_url=link,job_description=self.job_details)
        if not job_update_status and "duplicate key" in msg.get("message","").lower():
            print(f"Job already exists in db - {link}")
            return True
        elif not job_update_status:
            self.update_status("Failed", f"Database update error - {msg}")
            await self.send_status()
            self.print_status()
            return False
        else:
            self.payload.status = "Done"
            self.payload.category = category
            self.payload.url = link
            self.payload.job_details = self.job_details
            
            sent_status = await self.send_payload()
            if not sent_status:
                await self.send_status()
                self.print_status()
                return False
            else:
                self.job_counter.increment()
                print(f"Job {self.job_counter.get_count()} ------ {self.job_details}")  
                return True     
        
    async def scrape_login_page(self):
        best_match_button = await self.page.get_element('button[data-test="tab-best-matches"]')
        if best_match_button:
            await self.page.click(best_match_button)
            await asyncio.sleep(1)
            job_tiles = await self.page.get_all_elements('section[data-ev-sublocation="job_feed_tile"]')
            first_link = True
            for job_posting in job_tiles:
                job_posted_time_element = await job_posting.query_selector('span[data-test="posted-on"]')
                job_posted_time = await self.page.get_text_content(job_posted_time_element) if job_posted_time_element else "N/A"
                print(f"Job posted time: {job_posted_time.strip()}")
                link_div = await job_posting.query_selector('a[data-ev-label="link"]')
                link = await link_div.get_attribute('href')
                if not link:
                    self.status["status"] = "Failed"
                    self.status["message"] = "Problem extracting link ... \nMaybe the website structure has changed"
                    await self.send_status()
                    self.print_status()
                    return False
                link = upwork_url + link
                if first_link:
                    self.session_latest_links["Best Match"] = link
                    first_link = False
                if link == self.latest_links.get("Best Match",None) or \
                    ("minutes" not in job_posted_time.lower().split(sep=" ") and "minute" not in job_posted_time.lower().split(sep=" ")):
                    print(f"last_link in Best Match")
                    if link == self.latest_links.get("Best Match",None):
                        print("Exact link match found, stopping further scraping.")
                    break
                await self.page.click(link_div, wait_for='li[data-qa="client-location"] strong')
                
                scrape_success = await self.scrape_job_page()
                
                post_scraping_success = await self.post_scraping_tasks(scrape_success, link, "Best Match")
                if not post_scraping_success:
                    return False
                await asyncio.sleep(2)
                await self.page.go_back()
                await asyncio.sleep(2)
        return True
                
                
    def get_latest_links(self):
        return self.session_latest_links