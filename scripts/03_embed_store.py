import json                                                                                                                                                                                                         
import ssl                                                                                                                                                                                                          
from pathlib import Path                    
                                                                                                                                                                                                                    
import chromadb                         
import urllib.request                                                                                                                                                                                               
import yaml                                                                                                                                                                                                         
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
OLLAMA_URL = "http://localhost:11434/api/embeddings"                                                                                                                                                                
EMBED_MODEL = "nomic-embed-text"                                                                                                                                                                                    
BATCH_SIZE = 50                                                                                                                                                                                                     
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def load_config():                                                                                                                                                                                                  
    with open("config.yaml") as f:                                                                                                                                                                                  
        return yaml.safe_load(f)                                                                                                                                                                                    
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def get_embedding(text):                                                                                                                                                                                            
    """Get embedding from Ollama for a single text."""                                                                                                                                                              
    payload = json.dumps({                                                                                                                                                                                          
        "model": EMBED_MODEL,                                                                                                                                                                                       
        "prompt": text,                                                                                                                                                                                             
    }).encode("utf-8")                                                                                                                                                                                              
                                                                                                                                                                                                                    
    request = urllib.request.Request(                                                                                                                                                                               
        OLLAMA_URL,                                                                                                                                                                                                 
        data=payload,                                                                                                                                                                                               
        headers={"Content-Type": "application/json"},                                                                                                                                                               
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())                                                                                                                                                                        
        return result["embedding"]          
                                                                                                                                                                                                                    

# Build the text to embed — combines metadata with content for richer retrieval.                                                                                                                       
def build_embed_text(chunk):                                                                                                                                                                                        
    parts = []                                                                                                                                                                                                      
                                                                                                                                                                                                                    
    if chunk.get("title"):                                                                                                                                                                                          
        parts.append(f"Title: {chunk['title']}")                                                                                                                                                                    
    if chunk.get("section"):                                                                                                                                                                                        
        parts.append(f"Section: {chunk['section']}")                                                                                                                                                                
    if chunk.get("chunk_type") and chunk["chunk_type"] != "text":                                                                                                                                                   
        parts.append(f"Type: {chunk['chunk_type']}")                                                                                                                                                                
    if chunk.get("citation_key"):
        parts.append(f"Citation Key: {chunk['citation_key']}")
                                                                                                                                                                                                                    
    parts.append(chunk["content"])                                                                                                                                                                                  
                                                                                                                                                                                                                    
    # Include custom commands if present — helps embed notation context                                                                                                                                             
    if chunk.get("custom_commands"):                                                                                                                                                                                
        parts.append(f"Notation: {chunk['custom_commands'][:300]}")                                                                                                                                                 
                                                                                                                                                                                                                    
    return "\n".join(parts)                 
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def main():                                                                                                                                                                                                         
    chunks_path = Path("data/chunks/all_chunks.json")                                                                                                                                                               
    if not chunks_path.exists():                                                                                                                                                                                    
        print("No chunks found. Run 02_parse_chunk.py first.")
        return                                                                                                                                                                                                      
                                                                                                                                                                                                                    
    with open(chunks_path) as f:                                                                                                                                                                                    
        chunks = json.load(f)                                                                                                                                                                                       
                                                                                                                                                                                                                    
    print(f"Loaded {len(chunks)} chunks")                                                                                                                                                                           
                                        
    # Test Ollama connection                                                                                                                                                                                        
    try:                                                                                                                                                                                                            
        get_embedding("test")
        print("Ollama connection OK")                                                                                                                                                                               
    except Exception as error:              
        print(f"Cannot connect to Ollama: {error}")                                                                                                                                                                 
        print("Make sure Ollama is running: ollama serve")                                                                                                                                                          
        return                                                                                                                                                                                                      
                                                                                                                                                                                                                    
    # Initialize ChromaDB (persistent, file-based)                                                                                                                                                                  
    db_path = "data/chromadb"                                                                                                                                                                                       
    client = chromadb.PersistentClient(path=db_path)                                                                                                                                                                
                                                                                                                                                                                                                    
    # Create or get collection              
    collection = client.get_or_create_collection(                                                                                                                                                                   
        name="integrable_systems",                                                                                                                                                                                  
        metadata={"description": "Calogero-Moser and integrable systems papers"},                                                                                                                                   
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    # Check what's already stored (for resume support)                                                                                                                                                              
    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()                                                                                                                                
    print(f"Already in DB: {existing_ids.__len__()} chunks")                                                                                                                                                        
                                                                                                                                                                                                                    
    new_chunks = [c for c in chunks if c["chunk_id"] not in existing_ids]
    print(f"New to embed: {len(new_chunks)} chunks")                                                                                                                                                                
                                                                                                                                                                                                                    
    if not new_chunks:                                                                                                                                                                                              
        print("Nothing new to embed.")                                                                                                                                                                              
        return                                                                                                                                                                                                      
                                                                                                                                                                                                                    
    # Process in batches                                                                                                                                                                                            
    for i in range(0, len(new_chunks), BATCH_SIZE):                                                                                                                                                                 
        batch = new_chunks[i:i + BATCH_SIZE]
                                                                                                                                                                                                                    
        ids = []                            
        embeddings = []                                                                                                                                                                                             
        documents = []                                                                                                                                                                                              
        metadatas = []                                                                                                                                                                                              
                                                                                                                                                                                                                    
        for chunk in batch:                                                                                                                                                                                         
            embed_text = build_embed_text(chunk)                                                                                                                                                                    
                                                                                                                                                                                                                    
            try:                                                                                                                                                                                                    
                embedding = get_embedding(embed_text)                                                                                                                                                               
            except Exception as error:                                                                                                                                                                              
                print(f"  [ERROR] {chunk['chunk_id']}: {error}")                                                                                                                                                    
                continue                                                                                                                                                                                            
                                                                                                                                                                                                                    
            ids.append(chunk["chunk_id"])                                                                                                                                                                           
            embeddings.append(embedding)                                                                                                                                                                            
            documents.append(chunk["content"])                                                                                                                                                                      
            metadatas.append({                                                                                                                                                                                      
                "arxiv_id": chunk.get("arxiv_id", ""),
                "title": chunk.get("title", ""),                                                                                                                                                                    
                "authors": ", ".join(chunk.get("authors", [])),                                                                                                                                                     
                "section": chunk.get("section", ""),                                                                                                                                                                
                "chunk_type": chunk.get("chunk_type", ""),                                                                                                                                                          
                "is_style_paper": chunk.get("is_style_paper", False),                                                                                                                                               
            })                                                                                                                                                                                                      
                                                                                                                                                                                                                    
        if ids:                                                                                                                                                                                                     
            collection.add(                                                                                                                                                                                         
                ids=ids,                                                                                                                                                                                            
                embeddings=embeddings,                                                                                                                                                                              
                documents=documents,                                                                                                                                                                                
                metadatas=metadatas,                                                                                                                                                                                
            )                                                                                                                                                                                                       
                                                                                                                                                                                                                    
        done = min(i + BATCH_SIZE, len(new_chunks))                                                                                                                                                                 
        print(f"  Embedded {done}/{len(new_chunks)}")                                                                                                                                                               
                                                                                                                                                                                                                    
    print(f"\n{'=' * 50}")                                                                                                                                                                                          
    print(f"Total in DB: {collection.count()}")
    print(f"Stored at: {db_path}")                                                                                                                                                                                  
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
if __name__ == "__main__":                                                                                                                                                                                          
    main()               