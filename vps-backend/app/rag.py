import os
import json
import sqlite3
import numpy as np
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer

# Initialize the embedding model
# We use all-MiniLM-L6-v2 because it is extremely small (120MB), fast, and runs perfectly on CPU.
MODEL_NAME = "all-MiniLM-L6-v2"
model = None

def get_model():
    global model
    if model is None:
        model = SentenceTransformer(MODEL_NAME)
    return model

DB_PATH = os.path.join(os.path.dirname(__file__), "rag_database.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            content TEXT,
            embedding BLOB
        )
    """)
    conn.commit()
    conn.close()

def clear_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM document_chunks")
    conn.commit()
    conn.close()

def add_documents(documents: List[Dict[str, str]]):
    """
    documents: List of dicts, each having {'file_path': str, 'content': str}
    """
    if not documents:
        return
    
    # Initialize DB
    init_db()
    
    # Load model and compute embeddings
    embedder = get_model()
    contents = [doc['content'] for doc in documents]
    embeddings = embedder.encode(contents, show_progress_bar=False)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for doc, emb in zip(documents, embeddings):
        emb_bytes = emb.astype(np.float32).tobytes()
        cursor.execute(
            "INSERT INTO document_chunks (file_path, content, embedding) VALUES (?, ?, ?)",
            (doc['file_path'], doc['content'], emb_bytes)
        )
        
    conn.commit()
    conn.close()

def get_relevant_context(query: str, top_k: int = 3) -> List[Dict]:
    """
    Finds the most semantically similar chunks to the query using numpy cosine similarity.
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, content, embedding FROM document_chunks")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return []
    
    # Encode query
    embedder = get_model()
    query_emb = embedder.encode(query, convert_to_numpy=True) # shape (384,)
    
    results = []
    for file_path, content, emb_bytes in rows:
        emb = np.frombuffer(emb_bytes, dtype=np.float32) # shape (384,)
        # Calculate Cosine Similarity: (A . B) / (||A|| * ||B||)
        dot_product = np.dot(query_emb, emb)
        norm_q = np.linalg.norm(query_emb)
        norm_e = np.linalg.norm(emb)
        
        similarity = dot_product / (norm_q * norm_e) if (norm_q > 0 and norm_e > 0) else 0.0
        results.append({
            "file_path": file_path,
            "content": content,
            "similarity": float(similarity)
        })
        
    # Sort by similarity descending
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]
