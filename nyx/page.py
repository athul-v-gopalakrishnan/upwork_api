import random
import asyncio
from typing import Union, Optional

from playwright.async_api import Page, ElementHandle

from nyx.cursor import VisualGhostCursor

class NyxPage:
    def __init__(self, page: Page, cursor):
        self._page = page
        self.nyx_cursor = cursor
        
    @classmethod  
    async def page_with_tracking(cls, page:Page):
        """Initialize the visual cursor tracker for a given Playwright page"""
        nyx_cursor = await VisualGhostCursor.cursor_with_tracking(page)
        return cls(page=page, cursor=nyx_cursor)

    def __getattr__(self, name):
        # delegate unknown attributes to real Playwright page
        return getattr(self._page, name)
    
    async def goto(self, url: str, captcha_selector:Union[str,ElementHandle] = None, **kwargs):
        """Navigate to a URL"""
        kwargs.setdefault("timeout", 30000)
        try:
            await self._page.goto(url, **kwargs)
            self.nyx_cursor = await VisualGhostCursor.cursor_with_tracking(self._page)
            print(f"Navigated to {url}")
            if captcha_selector:
                await self.expect_and_solve_cloudfare_challenge(selector=captcha_selector)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Warning: Could not navigate to {url}: {e}")

    async def click(self, selector:Optional[Union[str, ElementHandle]]):
        """Perform a click with the visual cursor"""
        try:
            await self.nyx_cursor.cursor.click(selector=selector)
        except Exception as e:
            print(f"Warning: Could not perform visual click: {e}")
            
    async def scroll_by(self, scroll_length:int, randomness:bool = True):
        if randomness:
            random_scroll_length = random.randint(int(scroll_length*0.75), int(scroll_length*1.25))
            await self._page.evaluate(f"window.scrollBy({{ top: {random_scroll_length}, behavior: 'smooth' }});")
        else:
            await self._page.evaluate(f"window.scrollBy({{ top: {scroll_length}, behavior: 'smooth' }});")
            
    async def fill_field_and_enter(self, selector:Union[str, ElementHandle], text:str):
        """Fill a field and press Enter with the visual cursor"""
        try:
            await self.scroll_by(300)
            await self.nyx_cursor.cursor.click(selector=selector)
            await self._page.keyboard.press("Control+A")
            await self._page.keyboard.press("Backspace")
            await self._page.keyboard.type(text, delay=random.randint(10, 300))
            await self._page.keyboard.press("Enter")
        except Exception as e:
            print(f"Warning: Could not fill field and press Enter: {e}")
            
    async def check_for_element(self, selector:Union[str, ElementHandle]) -> bool:
        """Check if an element exists on the page"""
        try:
            element = await self._page.query_selector(selector=selector) if isinstance(selector, str) else selector
            print(f"Element found: {element}")
            return True if element else False
        except Exception as e:
            print(f"Warning: Could not check for element: {e}")
            return False
            
    async def get_text_content(self, selector:Union[str, ElementHandle]) -> Optional[str]:
        """Get text content of an element"""
        try:
            await self.scroll_by(300)
            element = await self._page.query_selector(selector) if isinstance(selector, str) else selector
            if element:
                return await element.text_content()
            else:
                print(f"Warning: Element not found for selector: {selector}")
                return None
        except Exception as e:
            print(f"Warning: Could not get text content: {e}")
            return None
        
    async def get_attribute(self, selector:Union[str, ElementHandle], attribute_name:str) -> Optional[str]:
        """Get attribute value of an element"""
        try:
            await self.scroll_by(300)
            element = await self._page.query_selector(selector) if isinstance(selector, str) else selector
            if element:
                return await element.get_attribute(attribute_name)
            else:
                print(f"Warning: Element not found for selector: {selector}")
                return None
        except Exception as e:
            print(f"Warning: Could not get attribute '{attribute_name}': {e}")
            return None
        
    async def get_element(self, selector:Union[str, ElementHandle]):
        try:
            await self.scroll_by(300)
            element = await self._page.query_selector(selector) if isinstance(selector, str) else selector
            return element
        except Exception as e:
            print(f"Warning: Could not get element '{selector}': {e}")
            return None 
        
    async def copy_to_clipboard(self, text: str):
        try:
            await self._page.evaluate("(text) => navigator.clipboard.writeText(text)", text)
        except Exception as e:
            print(f"Could not copy text : {e}")
            
    async def paste_from_clipboard(self, selector:Union[str, ElementHandle], to_enter:bool = False):
        try:
            await self.nyx_cursor.cursor.click(selector=selector)
            await self._page.keyboard.press("Control+v")
            if to_enter:
                await self._page.keyboard.press("Enter")
        except Exception as e:
            print(f"Warning: Could not fill field and press Enter: {e}")
        
    
    async def get_all_elements(self, selector:Union[str, ElementHandle]):
        try:
            elements = await self._page.query_selector_all(selector) if isinstance(selector, str) else selector
            return elements
        except Exception as e:
            print(f"Warning: Could not get element '{selector}': {e}")
            return None 
        
    async def expect_and_solve_cloudfare_challenge(self, selector:Union[str,ElementHandle] , timeout:int=15000):
        """Wait for and solve Cloudflare challenge if present"""
        try:
            await asyncio.sleep(10)
            # Wait for Cloudflare challenge to appear
            challenge_div = await self._page.query_selector(selector="div[class*='challenge-container']")
            print("\n\n",challenge_div,"\n\n")
            
            if challenge_div:
                print("Cloudflare challenge detected, waiting to be solved...")
                checkbox = await self._page.query_selector(selector=selector)
                print("\n\n",checkbox)
                if checkbox:
                    await self.nyx_cursor.captcha_click(checkbox)
                    
                    await self._page.wait_for_selector(selector, state='detached', timeout=60000)
                    print("Cloudflare challenge solved.")
                else:
                    print("Captcha found but check the selector provided.")
            else:
                print("No Cloudflare challenge detected.")
        except Exception as e:
            print(f"No Cloudflare challenge detected or error occurred: {e}")