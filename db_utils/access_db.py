import asyncpg
import asyncio

from upwork_agent.bidder_agent import Proposal

# Adjust these imports/values as needed for your project
from vault.db_config import dbname, username, password

async def create_proposals_table():
    pool = await asyncpg.create_pool(
        user=username,
        password=password,
        database=dbname,
        host="localhost"
    )
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id SERIAL PRIMARY KEY,
                job_url TEXT NOT NULL,
                proposal JSONB NOT NULL,
                applied BOOLEAN NOT NULL DEFAULT FALSE
            );
        """)
    await pool.close()
    
async def clear_proposals_table():
    pool = await asyncpg.create_pool(
        user=username,
        password=password,
        database=dbname,
        host="localhost"
    )
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM proposals;")
    await pool.close()
    
async def add_proposal(job_url: str, proposal:Proposal, applied: bool = False):
    """
    Insert a proposal into the proposals table.
    proposal_model: a Pydantic model instance.
    """
    try:
        pool = await asyncpg.create_pool(
            user=username,
            password=password,
            database=dbname,
            host="localhost"
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO proposals (job_url, proposal, applied)
                VALUES ($1, $2, $3)
                """,
                job_url,
                proposal.model_dump_json(),  # Convert Pydantic model to dict for JSONB
                applied
            )
        return True
    except Exception as e:
        return f"Pushing job {job_url} to db failed - {e}"
    finally:
        await pool.close()
        
async def get_proposal_by_url(job_url: str):
    """
    Retrieve a proposal row from the proposals table by job_url.
    Returns the row as a dict, or None if not found.
    """
    try:
        pool = await asyncpg.create_pool(
            user=username,
            password=password,
            database=dbname,
            host="localhost"
        )
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM proposals WHERE job_url = $1;", job_url
            )
            if row:
                proposal_json = row["proposal"]
                proposal = Proposal.model_validate_json(proposal_json)
                return proposal
            return None
    except Exception as e:
        print(f"Could not retrieve proposal - {e}")
    finally:
        await pool.close()
        
    
async def view_proposals_table(num_rows: int = 10):
    """
    View the first `num_rows` rows from the proposals table.
    """
    pool = await asyncpg.create_pool(
        user=username,
        password=password,
        database=dbname,
        host="localhost"
    )
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM proposals ORDER BY id LIMIT $1;", num_rows
        )
        for row in rows:
            print(dict(row))
    await pool.close()
    
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
        pool = await asyncpg.create_pool(
            user=username,
            password=password,
            database=dbname,
            host="localhost"
        )
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE proposals
                SET {set_clause}
                WHERE job_url = ${idx}
                """,
                *values
            )
        return "Update success."
    except Exception as e:
        return f"Update failed - {e}"
    finally:
        await pool.close()

if __name__ == "__main__":
    proposal = asyncio.run(get_proposal_by_url("https://www.upwork.com/jobs/~021970412083400789623?link=new_job&frkscc=YhGCmCy6THh5"))
    print(proposal)