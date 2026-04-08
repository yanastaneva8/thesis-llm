import argparse 
import sys                                                                                                                                                                                                          
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def cmd_fetch(args):                                                                                                                                                                                                
    from src.arxiv_client import fetch_papers                                                                                                                                                                       
    fetch_papers(max_override=args.max, dry_run=args.dry_run)                                                                                                                                                       
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def cmd_chunk(args):                                                                                                                                                                                                
    from src.chunker import process_all                                                                                                                                                                             
    process_all()                                                                                                                                                                                                   
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def cmd_embed(args):                                                                                                                                                                                                
    import json 
    from pathlib import Path                                                                                                                                                                                        
                                                                                                                                                                                                                    
    import chromadb                                                                                                                                                                                                 
                                                                                                                                                                                                                    
    from src.config import CHUNKS_DIR, CHROMADB_DIR                                                                                                                                                                 
    from src.ollama_client import get_embedding, is_available
                                                                                                                                                                                                                    
    chunks_path = CHUNKS_DIR / "all_chunks.json"                                                                                                                                                                    
    if not chunks_path.exists():                                                                                                                                                                                    
        print("No chunks found. Run 'chunk' first.")                                                                                                                                                                
        return                                                                                                                                                                                                      
                                                                                                                                                                                                                    
    if not is_available():                                                                                                                                                                                          
        print("Ollama is not running. Start it with: ollama serve")                                                                                                                                                 
        return                                                                                                                                                                                                      
                
    with open(chunks_path) as f:                                                                                                                                                                                    
        chunks = json.load(f)
                                                                                                                                                                                                                    
    print(f"Loaded {len(chunks)} chunks")                                                                                                                                                                           
                                                                                                                                                                                                                    
    CHROMADB_DIR.mkdir(parents=True, exist_ok=True)                                                                                                                                                                 
    client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
    collection = client.get_or_create_collection(                                                                                                                                                                   
        name="integrable_systems",                                                                                                                                                                                  
        metadata={"description": "Calogero-Moser and integrable systems papers"},                                                                                                                                   
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()                                                                                                                                
    new_chunks = [c for c in chunks if c["chunk_id"] not in existing_ids]
    print(f"Already embedded: {len(existing_ids)}, new: {len(new_chunks)}")                                                                                                                                         
                                                                                                                                                                                                                    
    batch_size = 50                                                                                                                                                                                                 
    for i in range(0, len(new_chunks), batch_size):                                                                                                                                                                 
        batch = new_chunks[i:i + batch_size]                                                                                                                                                                        
                                                                                                                                                                                                                    
        ids = []                                                                                                                                                                                                    
        embeddings = []                                                                                                                                                                                             
        documents = []                                                                                                                                                                                              
        metadatas = []                                                                                                                                                                                              
                                                                                                                                                                                                                    
        for chunk in batch:                                                                                                                                                                                         
            parts = []                                                                                                                                                                                              
            if chunk.get("title"):                                                                                                                                                                                  
                parts.append(f"Title: {chunk['title']}")                                                                                                                                                            
            if chunk.get("section"):                                                                                                                                                                                
                parts.append(f"Section: {chunk['section']}")                                                                                                                                                        
            if chunk.get("citation_key"):
                parts.append(f"Citation Key: {chunk['citation_key']}")
            parts.append(chunk["content"])                                                                                                                                                                          
            embed_text = "\n".join(parts)                                                                                                                                                                           
                                                                                                                                                                                                                    
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
                ids=ids, embeddings=embeddings,                                                                                                                                                                     
                documents=documents, metadatas=metadatas,                                                                                                                                                           
            )                                                                                                                                                                                                       
                                                                                                                                                                                                                    
        done = min(i + batch_size, len(new_chunks))                                                                                                                                                                 
        print(f"  Embedded {done}/{len(new_chunks)}")                                                                                                                                                               
                                                                                                                                                                                                                    
    print(f"Total in DB: {collection.count()}")                                                                                                                                                                     
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def cmd_topics(args):
    # Filenames starting with numbers (04_...) are difficult to import.
    # It is better to import the logic directly from src if available.
    # If you must use the script, you can use importlib:
    import importlib
    topic_module = importlib.import_module("scripts.04_discover_topics")
    
    # Import inline to avoid circular issues                                                                                                                                                                        
    import numpy as np                                                                                                                                                                                              
    import chromadb                                                                                                                                                                                                 
                                                                                                                                                                                                                    
    from src.config import CHROMADB_DIR                                                                                                                                                                             
                                                                                                                                                                                                                    
    client = chromadb.PersistentClient(path=str(CHROMADB_DIR))                                                                                                                                                      
    collection = client.get_collection("integrable_systems")
                                                                                                                                                                                                                    
    if collection.count() == 0:                                                                                                                                                                                     
        print("No embeddings found. Run 'embed' first.")                                                                                                                                                            
        return                                                                                                                                                                                                      
                
    results = collection.get(include=["embeddings", "metadatas", "documents"])                                                                                                                                      
    embeddings = np.array(results["embeddings"])
    metadatas = results["metadatas"]                                                                                                                                                                                
    documents = results["documents"]                                                                                                                                                                                
                                                                                                                                                                                                                    
    print(f"Clustering {len(embeddings)} chunks into {args.clusters} groups...\n")

    # Note: Ensure src/topic_discovery.py exists or use the logic from 04_discover_topics.py
    try:
        from src.topic_discovery import cluster_and_display
        cluster_and_display(embeddings, metadatas, documents, args.clusters)
    except ImportError:
        print("Error: src.topic_discovery not found. Ensure topic discovery logic is properly modularized.")
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def cmd_generate(args):                                                                                                                                                                                             
    from src.ollama_client import is_available                                                                                                                                                                      
                                                                                                                                                                                                                    
    if not is_available():                                                                                                                                                                                          
        print("Ollama is not running. Start it with: ollama serve")                                                                                                                                                 
        return                                                                                                                                                                                                      
                
    if args.outline_only:                                                                                                                                                                                           
        from src.generator import generate_outline
        sections = generate_outline(args.topic)                                                                                                                                                                     
        print("\nProposed outline:")                                                                                                                                                                                
        for i, title in enumerate(sections, 1):                                                                                                                                                                     
            print(f"  {i}. {title}")                                                                                                                                                                                
    else:                                                                                                                                                                                                           
        from src.generator import generate_paper                                                                                                                                                                    
        generate_paper(args.topic, args.sections, args.author)                                                                                                                                                      
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def cmd_pipeline(args):                                                                                                                                                                                             
    """Run the full pipeline end-to-end."""                                                                                                                                                                         
    from src.ollama_client import is_available                                                                                                                                                                      
                                                                                                                                                                                                                    
    if not is_available():                                                                                                                                                                                          
        print("Ollama is not running. Start it with: ollama serve")                                                                                                                                                 
        return                                                                                                                                                                                                      
                
    print("=== Step 1: Fetch papers ===")                                                                                                                                                                           
    cmd_fetch(argparse.Namespace(max=args.max, dry_run=False))
                                                                                                                                                                                                                    
    print("\n=== Step 2: Chunk papers ===")                                                                                                                                                                         
    cmd_chunk(argparse.Namespace())                                                                                                                                                                                 
                                                                                                                                                                                                                    
    print("\n=== Step 3: Embed chunks ===")                                                                                                                                                                         
    cmd_embed(argparse.Namespace())                                                                                                                                                                                 
                                                                                                                                                                                                                    
    print("\n=== Step 4: Generate paper ===")                                                                                                                                                                       
    cmd_generate(argparse.Namespace(                                                                                                                                                                                
        topic=args.topic,                                                                                                                                                                                           
        sections=args.sections,                                                                                                                                                                                     
        author=args.author,                                                                                                                                                                                         
        outline_only=False,                                                                                                                                                                                         
    ))                                                                                                                                                                                                              
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def main():                                                                                                                                                                                                         
    parser = argparse.ArgumentParser(
        description="RAG Review Paper Generator",                                                                                                                                                                   
        formatter_class=argparse.RawDescriptionHelpFormatter,                                                                                                                                                       
        epilog=__doc__,                                                                                                                                                                                             
    )                                                                                                                                                                                                               
    subparsers = parser.add_subparsers(dest="command", required=True)                                                                                                                                               
                                                                                                                                                                                                                    
    # fetch                                                                                                                                                                                                         
    fetch_parser = subparsers.add_parser("fetch", help="Download papers from arXiv")                                                                                                                                
    fetch_parser.add_argument("--max", type=int, default=None)                                                                                                                                                      
    fetch_parser.add_argument("--dry-run", action="store_true")                                                                                                                                                     
                                                                                                                                                                                                                    
    # chunk                                                                                                                                                                                                         
    subparsers.add_parser("chunk", help="Parse LaTeX into chunks")                                                                                                                                                  
                                                                                                                                                                                                                    
    # embed
    subparsers.add_parser("embed", help="Embed chunks into ChromaDB")                                                                                                                                               
                                                                                                                                                                                                                    
    # topics                                                                                                                                                                                                        
    topics_parser = subparsers.add_parser("topics", help="Discover topic clusters")                                                                                                                                 
    topics_parser.add_argument("--clusters", type=int, default=10)                                                                                                                                                  
                                                                                                                                                                                                                    
    # generate                                                                                                                                                                                                      
    gen_parser = subparsers.add_parser("generate", help="Generate the review paper")                                                                                                                                
    gen_parser.add_argument("--topic", type=str, required=True)                                                                                                                                                     
    gen_parser.add_argument("--sections", type=int, default=6)                                                                                                                                                      
    gen_parser.add_argument("--author", type=str, default="")                                                                                                                                                       
    gen_parser.add_argument("--outline-only", action="store_true")                                                                                                                                                  
                                                                                                                                                                                                                    
    # pipeline                                                                                                                                                                                                      
    pipe_parser = subparsers.add_parser("pipeline", help="Run everything end-to-end")                                                                                                                               
    pipe_parser.add_argument("--topic", type=str, required=True)                                                                                                                                                    
    pipe_parser.add_argument("--sections", type=int, default=6)                                                                                                                                                     
    pipe_parser.add_argument("--author", type=str, default="")                                                                                                                                                      
    pipe_parser.add_argument("--max", type=int, default=None)                                                                                                                                                       
                                                                                                                                                                                                                    
    args = parser.parse_args()                                                                                                                                                                                      
                                                                                                                                                                                                                    
    commands = {                                                                                                                                                                                                    
        "fetch": cmd_fetch,
        "chunk": cmd_chunk,                                                                                                                                                                                         
        "embed": cmd_embed,                                                                                                                                                                                         
        "topics": cmd_topics,                                                                                                                                                                                       
        "generate": cmd_generate,                                                                                                                                                                                   
        "pipeline": cmd_pipeline,                                                                                                                                                                                   
    }                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    commands[args.command](args)                                                                                                                                                                                    
                
                                                                                                                                                                                                                    
if __name__ == "__main__":
    main()                                                                                                                                                                                                          
                