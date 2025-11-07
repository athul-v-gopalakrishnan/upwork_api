import aiohttp, asyncio

async def wait_for_cdp(port=9222, timeout=10):
    for _ in range(timeout):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{port}/json/version") as r:
                    if r.status == 200:
                        return True
        except:
            pass
        await asyncio.sleep(1)
    raise RuntimeError("Chrome CDP not responding.")
