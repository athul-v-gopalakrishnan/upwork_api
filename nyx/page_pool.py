import asyncio
from typing import List

from nyx.page import NyxPage
from utils.constants import home_url

class PagePool:
    def __init__(self, pages: List[NyxPage], pagepool_name:str):
        self.name = pagepool_name
        self.pages = pages
        self.idle_pages = asyncio.Queue()
        for page in pages:
            self.idle_pages.put_nowait(page)
    
    async def get_idle_page(self) -> NyxPage:
        """Acquire a page from the pool."""
        return await self.idle_pages.get()
    
    async def release(self, page: NyxPage):
        """Release a page back to the pool."""
        await page.goto(home_url)
        await self.idle_pages.put(page)
    
    def size(self) -> int:
        """Get the total number of pages in the pool."""
        return len(self.pages)
    
    def idle_count(self) -> int:
        """Get the number of idle pages currently available."""
        return self.idle_pages.qsize()