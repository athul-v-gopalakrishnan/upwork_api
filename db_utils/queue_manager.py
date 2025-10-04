import asyncpg
import asyncio
import json
from asyncpg.utils import _quote_ident

from upwork_agent.bidder_agent import Proposal

# Adjust these imports/values as needed for your project
from vault.db_config import dbname, username, password

async def create_queue_table():
    try:
        pool = await asyncpg.create_pool(
            user=username,
            password=password,
            database=dbname,
            host="localhost"
        )
        async with pool.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id SERIAL PRIMARY KEY,
                task_type TEXT NOT NULL,
                payload JSONB,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- pending, processing, done, failed
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_queue_priority
            ON task_queue (priority DESC, created_at ASC);
        """)
        return True, "Created task_queue table"
    except Exception as e:
        return False, f"Could not create the task_queue table - {e}"
    finally:
        await pool.close()
        
async def enqueue_task(task_type:str, payload:dict=None, priority:int=0):
    try:
        pool = await asyncpg.create_pool(
            user=username,
            password=password,
            database=dbname,
            host="localhost"
        )
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO task_queue (task_type, payload, priority)
                VALUES ($1, $2, $3);
            """, task_type, json.dumps(payload) if payload else None, priority)
        return True, "Task enqueued successfully"
    except Exception as e:
        return False, f"Could not enqueue task - {e}"
    finally:
        await pool.close()
        
async def get_next_task():
    try:
        pool = await asyncpg.create_pool(
            user=username,
            password=password,
            database=dbname,
            host="localhost"
        )
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT * FROM task_queue
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """
                )
                if row:
                    await conn.execute(
                        "UPDATE task_queue SET status = 'processing', updated_at = NOW() WHERE id = $1",
                        row['id']
                    )
                    return dict(row)
                else:
                    return None
    except Exception as e:
        return False, f"Could not get task - {e}"
    finally:
        await pool.close()