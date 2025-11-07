from dotenv import load_dotenv
from traceback import print_exc
from typing import List
import os

import pandas as pd
import psycopg2
import asyncpg

from langchain_postgres import PGVector
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings

from db_utils.db_pool import get_pool,close_pool, init_pool, DB_CONNECTION_STRING, \
    POSTGRES_USER, POSTGRES_PASSWORD_RAW, POSTGRES_DB, POSTGRES_HOST

load_dotenv()

async def ensure_pgvector():
    conn = await asyncpg.connect(
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD_RAW,
        database=POSTGRES_DB,
        host=POSTGRES_HOST,
    )
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    await conn.close()


embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

def create_docs_from_csv(file_path):
    df = pd.read_csv(file_path)
    columns = df.columns.tolist()
    
    documents = []
    
    for _, row in df.iterrows():
        metadata = {}
        if "Project Description" in columns:
            content = row["Project Description"] if pd.notna(row["Project Description"]) else ""
        else:
            content = ""
        for col in columns:
            if col != "Project Description":
                metadata[col] = row[col] if pd.notna(row[col]) else ""
                
        documents.append(Document(page_content=content, metadata=metadata))
        
    return documents

def embed_documents(documents:List[Document]):
    try:
        PGVector.from_documents(
            documents=documents,
            embedding=embedding_model,
            collection_name="proposal_embeddings",
            connection=DB_CONNECTION_STRING
            )
        print(f"Successfully embedded {len(documents)} documents.")
    except Exception as e:
        print(f"Error embedding documents: {e}")
        
def retrieve_similar_documents(query:str, top_k:int=5):
    try:
        pg_vector = PGVector(
            collection_name="proposal_embeddings",
            embeddings=embedding_model,
            connection=DB_CONNECTION_STRING
        )
        results = pg_vector.similarity_search(query, k=top_k)
        return results
    except Exception as e:
        print(f"Error retrieving documents: {e}")
        return []
    
def clear_all_pgvector_data():
    conn = psycopg2.connect(
    dbname=dbname,
    user=username,
    password=password,
    host="localhost",
    port=5432
    )
    cur = conn.cursor()

    # Clear one collection
    collection_name = "proposal_embeddings"
    cur.execute("""
    DELETE FROM langchain_pg_embedding
    WHERE collection_id = (
        SELECT id FROM langchain_pg_collection
        WHERE name = %s
    )::uuid;
""", (collection_name,))

    cur.execute("""
        DELETE FROM langchain_pg_collection
        WHERE name = %s;
    """, (collection_name,))

    conn.commit()
    cur.close()
    conn.close()
    
def check_embeddings_exist():
    """Check if embeddings exist in the database"""
    try:
        data = retrieve_similar_documents("test", top_k=1)
        count = len(data)
        print("vector db check:", count>0)
        return count > 0
    except Exception as e:
        print(f"Error checking embeddings: {e}")
        print_exc()
        return False
    
if __name__ == "__main__":
    clear_all_pgvector_data()
    # status = check_embeddings_exist()
    # print(f"Embeddings exist: {status}")
    # embed_documents(create_docs_from_csv("data/proposals.csv"))
    # status = check_embeddings_exist()
    # print(f"Embeddings exist: {status}")