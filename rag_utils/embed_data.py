from urllib.parse import quote_plus
from dotenv import load_dotenv
from traceback import print_exc
from typing import List
import os

import pandas as pd
import psycopg2

from langchain_postgres import PGVector
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "neoitoUpwork")
POSTGRES_PASSWORD = quote_plus(os.getenv("POSTGRES_PASSWORD", "upwork.bot@neoito"))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "upwork_automation")

DB_CONNECTION_STRING = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


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