import os
import re
import sys
import argparse
import requests

DEFAULT_API_HOST = "https://qwen.thinkittelugu.in"
SECRET_KEY = "thinkittelugu-secure-rag-key-2026"

def clean_markdown(text: str) -> str:
    """
    Remove YAML frontmatter and clean up syntax.
    """
    # Remove frontmatter (between first --- and second ---)
    text = re.sub(r"^---[\s\S]+?---", "", text)
    
    # Remove HTML comments
    text = re.sub(r"<!--[\s\S]+?-->", "", text)
    
    # Basic cleanups
    text = text.strip()
    return text

def chunk_text(text: str, max_chars: int = 800, overlap: int = 150) -> list:
    """
    Splits text into chunks, prioritizing paragraph boundaries.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        # If adding this paragraph exceeds max limit and we already have content, store current chunk
        if len(current_chunk) + len(para) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            # Keep overlap by taking the last part of the current chunk
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            current_chunk = overlap_text + "\n\n" + para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
                
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

def parse_docs_directory(docs_dir: str) -> list:
    """
    Recursively scans the docs directory and parses all .md and .mdx files.
    """
    documents = []
    
    for root, dirs, files in os.walk(docs_dir):
        # Ignore hidden directories and node_modules
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        
        for file in files:
            if file.endswith(('.md', '.mdx')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        raw_content = f.read()
                        
                    clean_content = clean_markdown(raw_content)
                    if not clean_content:
                        continue
                        
                    # Split into chunks so we search specific sections instead of the whole file
                    chunks = chunk_text(clean_content)
                    
                    for idx, chunk in enumerate(chunks):
                        documents.append({
                            "file_path": f"{file_path}#chunk-{idx}",
                            "content": chunk
                        })
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
                    
    return documents

def main():
    parser = argparse.ArgumentParser(description="Parse local Docusaurus documentation and upload RAG index to VPS.")
    parser.add_argument("--host", default=DEFAULT_API_HOST, help="The API host URL (e.g. https://ai.thinkittelugu.in or http://89.116.20.170)")
    parser.add_argument("--secret", default=SECRET_KEY, help="The secure index RAG authentication key")
    args = parser.parse_args()
    
    # Locate docs directory (relative to this script's position)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.abspath(os.path.join(script_dir, "..", "think-it-telugu-docs", "docs"))
    
    if not os.path.exists(docs_dir):
        print(f"Error: Could not find Docusaurus docs directory at {docs_dir}")
        sys.exit(1)
        
    print(f"Scanning documents in {docs_dir}...")
    documents = parse_docs_directory(docs_dir)
    print(f"Found and parsed {len(documents)} document chunks.")
    
    if not documents:
        print("No document chunks found to index. Exiting.")
        sys.exit(0)
        
    # Send payload to API
    api_url = f"{args.host.rstrip('/')}/api/index"
    payload = {
        "documents": documents,
        "secret_key": args.secret
    }
    
    print(f"Uploading index to {api_url}...")
    try:
        response = requests.post(api_url, json=payload, timeout=90)
        if response.status_code == 200:
            result = response.json()
            print(f"Successfully indexed {result.get('indexed_count')} chunks on the server!")
        else:
            print(f"Failed to index. Server returned status code {response.status_code}: {response.text}")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Network connection failed: {e}")
        print("Ensure the VPS backend is running and the specified --host is correct.")
        sys.exit(1)

if __name__ == "__main__":
    main()
