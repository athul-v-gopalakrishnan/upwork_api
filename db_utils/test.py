import asyncpg
import asyncio

# Adjust these imports/values as needed for your project
# from vault.db_config import dbname, username, password

# async def show_first_ten_rows():
#     pool = await asyncpg.create_pool(
#         user=username,
#         password=password,
#         database=dbname,
#         host="localhost"
#     )
#     async with pool.acquire() as conn:
#         tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
#         table_names = [row['table_name'] for row in tables]
#         for table in table_names:
#             print(f"\nTable: {table}")
#             try:
#                 if table == "proposals":
#                     rows = await conn.fetch(f'SELECT * FROM "{table}" LIMIT 10;')
#                     for row in rows:
#                         print(dict(row))
#                     if not rows:
#                         print("  (no rows)")
#                     input("Enter to continue : ")
#             except Exception as e:
#                 print(f"  Error reading table: {e}")
#     await pool.close()

if __name__ == "__main__":
    print(int(1.3))