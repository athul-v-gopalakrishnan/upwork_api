# db_utils/db_pool.py
from urllib.parse import quote_plus
import asyncpg
import asyncio
import os

POSTGRES_USER = os.getenv("POSTGRES_USER", "neoitoUpwork")
POSTGRES_PASSWORD_RAW = os.getenv("POSTGRES_PASSWORD", "upwork.bot@neoito")
POSTGRES_PASSWORD_ENC = quote_plus(os.getenv("POSTGRES_PASSWORD", "upwork.bot@neoito"))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "upwork_automation")

DB_CONNECTION_STRING = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD_ENC}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


pool = None  # global singleton

async def init_pool():
    """Initialize the shared asyncpg connection pool."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD_RAW,
            database=POSTGRES_DB,
            host=POSTGRES_HOST,
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
