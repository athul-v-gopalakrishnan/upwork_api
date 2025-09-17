from dotenv import load_dotenv
from typing import List

from vault.db_config import DB_CONNECTION_STRING, dbname, username, password

import pandas as pd
import psycopg2

from langchain_postgres import PGVector
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings

load_dotenv()

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
    
if __name__ == "__main__":
    clear_all_pgvector_data()
    file_path = "data/proposals.csv"
    docs = create_docs_from_csv(file_path)
    embed_documents(docs)
    query = "Looking for a web developer proficient in Django and React."
    similar_docs = retrieve_similar_documents(query)
    for doc in similar_docs:
        print(doc.page_content)
        print(doc.metadata)
        print("-----")
        

