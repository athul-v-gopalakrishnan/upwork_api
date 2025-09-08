import random
from time import sleep
from typing import Union, Optional

from playwright.sync_api import Page, ElementHandle

from vendors.python_ghost_cursor.playwright_async import create_cursor, GhostCursor

from utils.js_scripts import get_cursor_tracking_script

class VisualGhostCursor:
    def __init__(self, page:Page, start:dict = None):
        self.page = page
        if start is None:
            start = {
                "x": random.randint(100,400),
                "y": random.randint(100,400)
                }   
        self.cursor = create_cursor(
            page = page,
            start=start
            )
        print(f"VisualGhostCursor initialized at {start}")
        
    @classmethod
    async def cursor_with_tracking(cls, page:Page):
        """Initialize the visual cursor tracker"""
        try:
            start = {
                "x": random.randint(100,400),
                "y": random.randint(100,400)
                }
            result = await page.evaluate(get_cursor_tracking_script(x=start["x"], y=start["y"]))
            print(f"Cursor tracking script injected at {start}")
            return cls(page=page,start=start)
        
        except Exception as e:
            print(f"Warning: Could not initialize cursor tracker: {e}")
            
    async def click(self, selector:Optional[Union[str, ElementHandle]]):
        """Perform a click with the visual cursor"""
        try:
            await self.cursor.click(selector=selector)
        except Exception as e:
            print(f"Warning: Could not perform visual click: {e}")
            
    async def captcha_click(self, selector:Optional[Union[str, ElementHandle]]):
        """Perform a click with the visual cursor"""
        try:
            await self.cursor.captcha_click(selector=selector)
        except Exception as e:
            print(f"Warning: Could not perform visual click: {e}")