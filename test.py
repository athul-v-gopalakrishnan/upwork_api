from nyx.browser import NyxBrowser

import asyncio
from utils.constants import cloudfare_challenge_div_id

async def main():
    try:
        browser = NyxBrowser()
        await browser.start()
        page = await browser.new_page(
            goto="https://www.upwork.com/jobs/~021963093997174563048?link=new_job&frkscc=w7FghD0jxnLo",
            page_kwargs={"wait_until":"domcontentloaded",
            "referer":"https://www.upwork.com/nx/find-work/",},
            captcha_selector="#LsMgo8"
            )  
        input("Press Enter to close the browser...")
        await browser.shutdown()
    except Exception as e:
        await browser.shutdown()
    finally:
        await browser.shutdown()
    
if __name__ == "__main__":
    asyncio.run(main())