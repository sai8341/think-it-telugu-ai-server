import os
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.rag import add_documents, clear_db, get_relevant_context

app = FastAPI(title="Think IT Telugu AI Service API")

# Enable CORS so our Docusaurus frontend can call the VPS API directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, you can restrict this to ["https://thinkittelugu.in", "http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("MODEL_NAME", "qwen2.5:3b")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatMessage]] = []

class DocumentItem(BaseModel):
    file_path: str
    content: str

class IndexRequest(BaseModel):
    documents: List[DocumentItem]
    secret_key: str  # Basic authentication to prevent unauthorized index modifications

INDEX_SECRET = os.environ.get("INDEX_SECRET", "thinkittelugu-secure-rag-key-2026")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "model": DEFAULT_MODEL, "ollama_host": OLLAMA_HOST}

@app.post("/api/index")
def index_documents(req: IndexRequest):
    if req.secret_key != INDEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized secret key")
    
    try:
        clear_db()
        docs = [{"file_path": doc.file_path, "content": doc.content} for doc in req.documents]
        add_documents(docs)
        return {"status": "success", "indexed_count": len(docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(req: ChatRequest):
    query = req.query
    
    # 1. Retrieve matching context from RAG
    try:
        context_items = get_relevant_context(query, top_k=3)
    except Exception as e:
        context_items = []
        print(f"RAG search error: {e}")
        
    # Format the context block
    context_str = ""
    if context_items:
        context_str = "\n\nRelevant documentation:\n"
        for idx, item in enumerate(context_items):
            # Clean paths for cleaner display
            clean_path = item['file_path'].replace("\\", "/").split("docs/")[-1]
            context_str += f"[{idx+1}] Source: {clean_path}\n{item['content']}\n\n"
            
    # 2. Build the system prompt
    system_prompt = (
        "You are 'Mawa', a friendly, encouraging AI coding helper for 'Think IT Telugu'. "
        "Your goal is to explain programming concepts to beginners in a very simple, jargon-free way. "
        "You MUST respond in a natural mix of Telugu and English (Teluglish). "
        "Use funny analogies, friendly words (like 'mawa', 'brother', 'malli cheptha vinu'), and formatted code blocks where appropriate. "
        "Use the following documentation context to base your answers on. If the question is not about the documentation, "
        "answer it in the same friendly Teluglish coding tutor persona.\n"
        "-------------------\n"
        f"{context_str}"
        "-------------------\n"
        "Answer the student's question based on the provided context if relevant, keeping explanations clear and concise."
    )
    
    # 3. Assemble message history for Ollama
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history
    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})
        
    # Add current query
    messages.append({"role": "user", "content": query})
    
    # 4. Stream response from Ollama
    async def stream_generator():
        ollama_url = f"{OLLAMA_HOST}/api/chat"
        payload = {
            "model": DEFAULT_MODEL,
            "messages": messages,
            "stream": True
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", ollama_url, json=payload) as response:
                    if response.status_code != 200:
                        yield f"data: {json.dumps({'error': 'Ollama connection failed'})}\n\n"
                        return
                        
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                token = chunk.get("message", {}).get("content", "")
                                done = chunk.get("done", False)
                                
                                # Send as SSE format
                                yield f"data: {json.dumps({'text': token, 'done': done})}\n\n"
                            except Exception:
                                continue
        except Exception as e:
            yield f"data: {json.dumps({'error': f'Backend error: {str(e)}'})}\n\n"
            
    return StreamingResponse(stream_generator(), media_type="text/event-stream")
