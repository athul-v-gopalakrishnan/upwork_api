import subprocess
import asyncio
from playwright.async_api import async_playwright, Page, ElementHandle
from typing import Union, Optional

from nyx.page import NyxPage
from utils.constants import cdp_url, cdp_port, chrome_executable_path, user_data_dir

class NyxBrowser:
    def __init__(self, cdp_url=cdp_url, port=cdp_port):
        self.cdp_url = cdp_url
        self.port = port
        self.chrome_process = None
        self.engine = None
        self.num_pages = 0
        self.num_contexts = 0
        
    async def start(self):
        """Start Chrome subprocess and connect via CDP."""
        # Launch Chrome with remote debugging
        self.chrome_process = subprocess.Popen([
            chrome_executable_path,
            f'--user-data-dir={user_data_dir}',
            # "--headless=new",
            # "--disable-gpu",
            '--remote-debugging-port=9222',
            '--no-first-run',
            '--no-default-browser-check',
            "--disable-blink-features=AutomationControlled",
            #  "--disable-software-rasterizer",
            # "--disable-gpu-compositing",
            "--disable-infobars",
            "--start-maximized",
            "--no-sandbox",
            "--disable-dev-shm-usage"
        ] ,stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        # Give Chrome time to boot
        await asyncio.sleep(2)

        # Connect with Playwright
        self.playwright = await async_playwright().start()
        self.engine = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
        
    async def new_page(self, goto = None,captcha_selector:Union[str,ElementHandle] = None, page_kwargs: dict = None, goto_kwargs: dict = None,):
        """Create a new browser page (tab)."""
        if not self.engine:
            raise RuntimeError("Browser not started")
        if self.num_pages == 0:
            try:
                page = self.engine.contexts[0].pages[0]
                page = await NyxPage.page_with_tracking(page)
                self.num_pages += 1
            except Exception as e:
                raise RuntimeError(f"An unexpected error occured while creating page - {e}")
        else:
            try:
                page = await self.engine.contexts[0].new_page(**(page_kwargs or {}))
                page = await NyxPage.page_with_tracking(page)
                self.num_pages += 1
            except Exception as e:
                raise RuntimeError(f"An unexpected error occured while creating page - {e}")
        if goto:
            await page.goto(goto, **(goto_kwargs or {}))
            print(f"Navigated to {goto}")
            if captcha_selector:
                await page.expect_and_solve_cloudfare_challenge(selector=captcha_selector)
            await asyncio.sleep(2)
        return page
    
    async def new_context(self, **kwargs):
        if not self.engine:
            raise RuntimeError("Browser not started")
        if self.num_contexts == 0:
            try:
                context = self.engine.contexts[0]
                self.num_contexts += 1
            except Exception as e:
                raise RuntimeError(f"An unexpected error occured while creating context - {e}")
        else:
            try:
                context = await self.engine.new_context(**kwargs)
                self.num_contexts += 1
            except Exception as e:
                raise RuntimeError(f"An unexpected error occured while creating context - {e}")
        return context
    
    async def shutdown(self):
        """Close Playwright + kill Chrome process."""
        if self.engine:
            await self.engine.close()
        if self.playwright:
            await self.playwright.stop()
        if self.chrome_process:
            self.chrome_process.terminate()
            self.chrome_process.wait()