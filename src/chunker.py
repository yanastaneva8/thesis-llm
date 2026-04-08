import json                                                                                                                                                                                                         
import re
from pathlib import Path                                                                                                                                                                                            
                                                                                                                                                                                                                    
from src.config import METADATA_DIR, CHUNKS_DIR, STYLE_DIR                                                                                                                                                          
from src.latex_parser import (
    find_main_tex,                                                                                                                                                                                                  
    resolve_inputs,                                                                                                                                                                                                 
    strip_comments,                                                                                                                                                                                                 
    extract_body,                                                                                                                                                                                                   
    extract_preamble_commands,                                                                                                                                                                                      
    split_sections,                                                                                                                                                                                                 
    split_environments,                                                                                                                                                                                             
    split_long_chunk,                                                                                                                                                                                               
    MIN_CHUNK_CHARS,                                                                                                                                                                                                
)                                                                                                                                                                                                                   
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def chunk_paper(paper_dir, metadata, is_style_paper=False):
    """Process one paper into chunks."""                                                                                                                                                                            
    main_tex = find_main_tex(paper_dir)                                                                                                                                                                             
    if main_tex is None:                                                                                                                                                                                            
        return []                                                                                                                                                                                                   
                                                                                                                                                                                                                    
    try:                                                                                                                                                                                                            
        raw_text = main_tex.read_text(errors="ignore")                                                                                                                                                              
    except Exception:                                                                                                                                                                                               
        return []                                                                                                                                                                                                   
                                                                                                                                                                                                                    
    raw_text = resolve_inputs(raw_text, paper_dir)                                                                                                                                                                  
    custom_commands = extract_preamble_commands(raw_text)
    text = strip_comments(raw_text)                                                                                                                                                                                 
    body = extract_body(text)                                                                                                                                                                                       
                                                                                                                                                                                                                    
    if len(body) < MIN_CHUNK_CHARS:                                                                                                                                                                                 
        return []                                                                                                                                                                                                   
                                                                                                                                                                                                                    
    sections = split_sections(body)                                                                                                                                                                                 
    chunks = []
    chunk_index = 0                                                                                                                                                                                                 
                                                                                                                                                                                                                    
    for section_title, section_content in sections:                                                                                                                                                                 
        env_chunks = split_environments(section_content)                                                                                                                                                            
                                                                                                                                                                                                                    
        for chunk_type, chunk_text in env_chunks:                                                                                                                                                                   
            sub_chunks = split_long_chunk(chunk_text)                                                                                                                                                               
                                                                                                                                                                                                                    
            for sub_chunk in sub_chunks:                                                                                                                                                                            
                if len(sub_chunk) < MIN_CHUNK_CHARS:                                                                                                                                                                
                    continue                                                                                                                                                                                        
                                                                                                                                                                                                                    
                chunk = {                                                                                                                                                                                           
                    "chunk_id": f"{metadata.get('arxiv_id', 'style')}_{chunk_index}",                                                                                                                               
                    "arxiv_id": metadata.get("arxiv_id", ""),                                                                                                                                                       
                    "title": metadata.get("title", ""),                                                                                                                                                             
                    "authors": metadata.get("authors", []),                                                                                                                                                         
                    "section": section_title,                                                                                                                                                                       
                    "chunk_type": chunk_type,                                                                                                                                                                       
                    "chunk_index": chunk_index,                                                                                                                                                                     
                    "content": sub_chunk,                                                                                                                                                                           
                    "citation_key": generate_citation_key(metadata), # Add a suggested citation key
                    "custom_commands": custom_commands,                                                                                                                                                             
                    "is_style_paper": is_style_paper,                                                                                                                                                               
                }                                                                                                                                                                                                   
                chunks.append(chunk)                                                                                                                                                                                
                chunk_index += 1                                                                                                                                                                                    
                                                                                                                                                                                                                    
    return chunks                                                                                                                                                                                                   
                                                                                                                                                                                                                    
def generate_citation_key(metadata):
    """Generates a simple citation key from metadata (e.g., AuthorYear)."""
    author_surname = metadata["authors"][0].split(" ")[-1] if metadata["authors"] else "Anon"
    year = metadata.get("published", "YYYY-MM-DD").split("-")[0] # Use get with default for safety
    # Ensure the key is LaTeX-safe (no special characters)
    return re.sub(r'[^a-zA-Z0-9]', '', f"{author_surname}{year}")


                                                                                                                                                                                                                    
def process_all():
    """Process all arXiv + style papers into chunks."""                                                                                                                                                             
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)                                                                                                                                                                   
                                                                                                                                                                                                                    
    manifest_path = METADATA_DIR / "manifest.json"                                                                                                                                                                  
    if not manifest_path.exists():                                                                                                                                                                                  
        print("No manifest found. Run fetch first.")                                                                                                                                                                
        return []                                                                                                                                                                                                   
                                                                                                                                                                                                                    
    with open(manifest_path) as f:                                                                                                                                                                                  
        papers = json.load(f)                                                                                                                                                                                       
                                                                                                                                                                                                                    
    all_chunks = []                                                                                                                                                                                                 
                                                                                                                                                                                                                    
    # arXiv papers                                                                                                                                                                                                  
    print("Processing arXiv papers...")
    for paper in papers:                                                                                                                                                                                            
        paper_dir = Path(paper["source_dir"])                                                                                                                                                                       
        if not paper_dir.exists():                                                                                                                                                                                  
            continue                                                                                                                                                                                                
        chunks = chunk_paper(paper_dir, paper, is_style_paper=False)                                                                                                                                                
        all_chunks.extend(chunks)                                                                                                                                                                                   
        if chunks:                                                                                                                                                                                                  
            print(f"  {paper['arxiv_id']}: {len(chunks)} chunks")                                                                                                                                                   
                                                                                                                                                                                                                    
    # Style papers                                                                                                                                                                                                  
    if STYLE_DIR.exists():                                                                                                                                                                                          
        print("\nProcessing style papers...")                                                                                                                                                                       
        for tex_file in STYLE_DIR.rglob("*.tex"):                                                                                                                                                                   
            paper_dir = tex_file.parent                                                                                                                                                                             
            metadata = {                                                                                                                                                                                            
                "arxiv_id": f"style_{tex_file.stem}",                                                                                                                                                               
                "title": tex_file.stem,                                                                                                                                                                             
                "authors": ["self"],                                                                                                                                                                                
            }                                                                                                                                                                                                       
            chunks = chunk_paper(paper_dir, metadata, is_style_paper=True)                                                                                                                                          
            all_chunks.extend(chunks)                                                                                                                                                                               
            if chunks:                                                                                                                                                                                              
                print(f"  [STYLE] {tex_file.name}: {len(chunks)} chunks")                                                                                                                                           
                                                                                                                                                                                                                    
    # Save                                                                                                                                                                                                          
    output_path = CHUNKS_DIR / "all_chunks.json"                                                                                                                                                                    
    with open(output_path, "w") as f:                                                                                                                                                                               
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)                                                                                                                                                      
                                                                                                                                                                                                                    
    print(f"\nTotal chunks: {len(all_chunks)}")                                                                                                                                                                     
    return all_chunks                                                                                                                                                                                               
                                                                                                                                                                                                                    
