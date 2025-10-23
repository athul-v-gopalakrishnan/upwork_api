import asyncpg
import asyncio
import json
from asyncpg.utils import _quote_ident

from upwork_agent.bidder_agent import Proposal

from db_utils.db_pool import get_pool,close_pool, init_pool


import asyncpg
from datetime import datetime


class PromptArchive:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def init(self):
        self.pool = await get_pool()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id SERIAL PRIMARY KEY,
                    prompt_name TEXT NOT NULL,
                    version INT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT FALSE,
                    UNIQUE (prompt_name, version)
                );
                CREATE INDEX IF NOT EXISTS idx_prompts_name_active ON prompts (prompt_name, is_active);
            """)

    async def add_prompt(self, prompt_name: str, prompt_text: str) -> int:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                latest = await conn.fetchval(
                    "SELECT MAX(version) FROM prompts WHERE prompt_name=$1", prompt_name
                )
                new_version = (latest or 0) + 1

                # deactivate previous
                await conn.execute(
                    "UPDATE prompts SET is_active=FALSE WHERE prompt_name=$1", prompt_name
                )

                # insert new version
                await conn.execute("""
                    INSERT INTO prompts (prompt_name, version, prompt_text, is_active)
                    VALUES ($1, $2, $3, TRUE)
                """, prompt_name, new_version, prompt_text)

                return new_version

    async def get_active_prompt(self, prompt_name: str) -> str | None:
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM prompts WHERE prompt_name=$1 AND is_active=TRUE", prompt_name
            )
            return record["prompt_text"] if record else None

    async def rollback(self, prompt_name: str, version: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval(
                    "SELECT 1 FROM prompts WHERE prompt_name=$1 AND version=$2",
                    prompt_name, version
                )
                if not exists:
                    raise ValueError("Version not found")

                await conn.execute(
                    "UPDATE prompts SET is_active=FALSE WHERE prompt_name=$1", prompt_name
                )
                await conn.execute(
                    "UPDATE prompts SET is_active=TRUE WHERE prompt_name=$1 AND version=$2",
                    prompt_name, version
                )

    async def list_versions(self, prompt_name: str) -> list[dict]:
        async with self.pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT version, is_active, created_at
                FROM prompts
                WHERE prompt_name=$1
                ORDER BY version DESC
            """, prompt_name)
            return [dict(r) for r in records]
        
    async def clear_prompts(self):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM prompts;")

if __name__ == "__main__":
    async def main():
        await init_pool()
        pa = PromptArchive()
        await pa.init()
        v1 = await pa.add_prompt("greeting", "Hello, how can I help you?")
        v2 = await pa.add_prompt("greeting", "Hi there! What can I do for you?")
        active = await pa.get_active_prompt("greeting")
        print("Active Prompt:", active)
        versions = await pa.list_versions("greeting")
        print("All Versions:", versions)
        await pa.rollback("greeting", v1)
        active_after_rollback = await pa.get_active_prompt("greeting")
        print("Active Prompt after rollback:", active_after_rollback)
        await pa.clear_prompts()
        active = await pa.get_active_prompt("greeting")
        print("Active Prompt:", active)
        await close_pool()

    asyncio.run(main())
    