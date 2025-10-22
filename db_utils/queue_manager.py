import asyncpg
import asyncio
import json
from asyncpg.utils import _quote_ident

# Adjust these imports/values as needed for your project
from vault.db_config import dbname, username, password

from db_utils.db_pool import get_pool,close_pool, init_pool

async def create_queue_table():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id SERIAL PRIMARY KEY,
                task_type TEXT NOT NULL,
                payload JSONB,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- pending, processing, done, failed, aborted_via_restart
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
    
async def enqueue_task(task_type:str, payload=None, priority:int=0):
    try:
        print(f" from db : Enqueueing task: {task_type} with payload: {payload} and priority: {priority}")
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO task_queue (task_type, payload, priority)
                VALUES ($1, $2, $3);
            """, task_type, payload, priority)
        return True, "Task enqueued successfully"
    except Exception as e:
        return False, f"Could not enqueue task - {e}"
        
async def get_next_task():
    try:
        pool = await get_pool()
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
                    return True, dict(row)
                else:
                    return False, "No pending tasks"
    except Exception as e:
        return False, f"Could not get task - {e}"
    
async def main():
    await init_pool()
    success, message = await get_next_task()
    await view_queue_table(5)
    print(message)
    await close_pool()
    
async def view_queue_table(num_rows: int = 10):
    """
    View the first `num_rows` rows from the task_queue table.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM task_queue ORDER BY id LIMIT $1;", num_rows
        )
        for row in rows:
            print(dict(row))
            
async def update_task_status(task_id:int, status:str):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE task_queue SET status = $1, updated_at = NOW() WHERE id = $2",
                status, task_id
            )
        return True, "Task status updated successfully"
    except Exception as e:
        return False, f"Could not update task status - {e}"
    
async def abort_tasks_on_restart(task_type: str = "check_for_jobs"):
    """
    Mark pending/processing tasks of the given task_type as 'aborted via restart'.
    Returns (True, message) or (False, error_message).
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE task_queue
                SET status = 'aborted_via_restart', updated_at = NOW()
                WHERE task_type = $1 AND status IN ('pending', 'processing');
                """,
                task_type
            )
            # result is like "UPDATE <n>"
            try:
                affected = int(result.split()[-1])
            except Exception:
                affected = 0
        return True, f"Marked {affected} '{task_type}' tasks as aborted via restart"
    except Exception as e:
        return False, f"Could not mark tasks as aborted - {e}"
    
if __name__ == "__main__":
    asyncio.run(main())
