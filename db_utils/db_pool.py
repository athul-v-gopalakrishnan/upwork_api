# db_utils/db_pool.py
import asyncpg
import asyncio
from vault.db_config import dbname, username, password

pool = None  # global singleton

async def init_pool():
    """Initialize the shared asyncpg connection pool."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            user=username,
            password=password,
            database=dbname,
            host="localhost",
            min_size=1,
            max_size=10,
        )

async def get_pool():
    """Get the current connection pool."""
    global pool
    if pool is None:
        raise RuntimeError("Connection pool not initialized. Call init_pool() first.")
    return pool

async def close_pool():
    """Gracefully close the pool."""
    global pool
    if pool:
        await pool.close()
        pool = None
