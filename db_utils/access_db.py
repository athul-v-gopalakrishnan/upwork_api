import asyncpg
import asyncio
import json
from asyncpg.utils import _quote_ident

from upwork_agent.bidder_agent import Proposal

from db_utils.db_pool import get_pool,close_pool, init_pool

# Adjust these imports/values as needed for your project
from vault.db_config import dbname, username, password

async def create_proposals_table():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    id SERIAL PRIMARY KEY,
                    job_uuid bigint UNIQUE,
                    job_url TEXT NOT NULL UNIQUE,
                    job_type TEXT,
                    proposal JSONB NOT NULL,
                    applied BOOLEAN NOT NULL DEFAULT FALSE,
                    approved_by TEXT
                );
            """)
        return True, "Created proposals table"
    except Exception as e:
        return False, f"Could not create the jobs table - {e}"
    
async def create_jobs_table():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    job_uuid bigint UNIQUE,
                    job_url TEXT NOT NULL UNIQUE,
                    job_description JSONB NOT NULL
                );
            """)
        return True, "Created jobs table"
    except Exception as e:
        return False, f"Could not create the jobs table - {e}"
    
async def clear_proposals_table():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM proposals;")
        return True, "Cleared proposals table"
    except Exception as e:
        return False, f"Couldnot clear table - {e}"
    finally:
        await pool.close()
    
async def clear_jobs_table():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM jobs;")
        return True, "Cleared jobs table"
    except Exception as e:
        return False, f"Couldnot clear table - {e}"
    
async def add_proposal(uuid:int, job_url: str, job_type:str, proposal:Proposal, applied: bool = False, approved_by: str = None):
    """
    Insert a proposal into the proposals table.
    proposal_model: a Pydantic model instance.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO proposals (job_uuid, job_url, job_type, proposal, applied,approved_by)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid,
                job_url,
                job_type,
                proposal.model_dump_json(),  # Convert Pydantic model to dict for JSONB
                applied,
                approved_by
            )
        return True, {"status":"Done", "message" : "Proposal added successfully"}
    except asyncpg.UniqueViolationError:
        return False, {"status":"Exists", "message":"Proposal already exists"}
    except Exception as e:
        return False, {"status" : "Failed", "message" : f"Pushing job {job_url} to db failed - {e}"}
        
async def add_job(uuid:int, job_url: str, job_description:dict):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (job_uuid, job_url, job_description)
                VALUES ($1, $2, $3)
                """,
                uuid,
                job_url,
                json.dumps(job_description)
            )
        return True, {"status":"Job added successfully"}
    except asyncpg.UniqueViolationError:
        return True, {"status":"Exists", "message":"Job already exists"}
    except Exception as e:
        return False, {"status":"Failed", "message" : f"Pushing job {job_url} to db failed - {e}"}
        
async def get_proposal_by_url(job_url: str):
    """
    Retrieve a proposal row from the proposals table by job_url.
    Returns the proposal object, or None if not found.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM proposals WHERE job_url = $1;", job_url
            )
            if row:
                proposal_json = row["proposal"]
                proposal = Proposal.model_validate_json(proposal_json)
                job_type = row["job_type"]
                return proposal, job_type
            return None, None
    except Exception as e:
        print(f"Could not retrieve proposal - {e}")
        return None, None
        
async def get_job_by_url(job_url: str):
    """
    Retrieve a job row from the jobs table by job_url.
    Returns the row as a dict, or None if not found.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM jobs WHERE job_url = $1;", job_url
            )
            if row:
                job_description = row["job_description"]
                print(job_description)
                job_uuid = row["job_uuid"]
                return job_uuid, json.loads(job_description)
            return None, None
    except Exception as e:
        print(f"Could not retrieve proposal - {e}")
        return None, None
    
async def view_proposals_table(num_rows: int = 10):
    """
    View the first `num_rows` rows from the proposals table.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM proposals ORDER BY id LIMIT $1;", num_rows
        )
        for row in rows:
            print(dict(row))
    
async def view_jobs_table(num_rows: int = 10):
    """
    View the first `num_rows` rows from the jobs table.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM jobs ORDER BY id LIMIT $1;", num_rows
        )
        for row in rows:
            print(dict(row))
    
async def view_tasks_table(num_rows: int = 10):
    """
    View the first `num_rows` rows from the jobs table.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM task_queue ORDER BY id LIMIT $1;", num_rows
        )
        for row in rows:
            print(dict(row))
    
async def update_proposal_by_url(job_url: str, updates: dict):
    """
    Update fields in the proposals table for a given job_url.
    `updates` should be a dict of {column_name: new_value}.
    """
    try:
        if not updates:
            return "No updates provided."
        set_clauses = []
        values = []
        idx = 1
        for col, val in updates.items():
            set_clauses.append(f"{col} = ${idx}")
            values.append(val)
            idx += 1
        set_clause = ", ".join(set_clauses)
        values.append(job_url)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE proposals
                SET {set_clause}
                WHERE job_url = ${idx}
                """,
                *values
            )
        return True, "Update success."
    except Exception as e:
        return False, f"Update failed - {e}"
    
async def update_proposal_by_uuid(job_uuid: str, updates: dict):
    """
    Update fields in the proposals table for a given job_url.
    `updates` should be a dict of {column_name: new_value}.
    """
    try:
        if not updates:
            return "No updates provided."
        set_clauses = []
        values = []
        idx = 1
        for col, val in updates.items():
            set_clauses.append(f"{col} = ${idx}")
            values.append(val)
            idx += 1
        set_clause = ", ".join(set_clauses)
        values.append(job_uuid)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE proposals
                SET {set_clause}
                WHERE job_uuid = ${idx}
                """,
                *values
            )
        return True, "Update success."
    except Exception as e:
        return False, f"Update failed - {e}"
        
async def drop_table(table_name:str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"DROP TABLE IF EXISTS {_quote_ident(table_name)};")
    
async def check_table_schema(table_name: str):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Query column names and data types
            result = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = $1;
            """, table_name)
            # Format result as a list of dicts
            schema = [{"column": row['column_name'], "type": row['data_type']} for row in result]
            return True, {"status": "Schema retrieved", "schema": schema}
    except Exception as e:
        return False, {"status": f"Failed to check schema for {table_name} - {e}", "schema": []}
    
async def main():
    await init_pool()
    await drop_table("proposals")
    await drop_table("jobs")
    status, message = await create_jobs_table()
    status, message = await create_proposals_table()
    await view_jobs_table(5)
    await view_proposals_table(5)
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())