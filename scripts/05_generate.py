import argparse                                                                                                                                                                                                     
import json     
import re                                                                                                                                                                                                           
import urllib.request                                                                                                                                                                                               
from datetime import date                                                                                                                                                                                           
from pathlib import Path                                                                                                                                                                                            
                                                                                                                                                                                                                    
import chromadb                                                                                                                                                                                                     
import yaml                                                                                                                                                                                                         
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
OLLAMA_URL = "http://localhost:11434/api/generate"                                                                                                                                                                  
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"                                                                                                                                                          
LLM_MODEL = "mistral"                                                                                                                                                                                               
EMBED_MODEL = "nomic-embed-text"                                                                                                                                                                                    
                                                                                                                                                                                                                    
# Context budget — keep prompts under this to fit in 8GB RAM                                                                                                                                                        
MAX_CONTEXT_CHARS = 3000                                                                                                                                                                                            
MAX_STYLE_CHARS = 1500                                                                                                                                                                                              
TOP_K_CHUNKS = 4                                                                                                                                                                                                    
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def load_config():                                                                                                                                                                                                  
    with open("config.yaml") as f:                                                                                                                                                                                  
        return yaml.safe_load(f)                                                                                                                                                                                    
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def ollama_generate(prompt, temperature=0.7):                                                                                                                                                                       
    """Call Ollama local LLM."""                                                                                                                                                                                    
    payload = json.dumps({                                                                                                                                                                                          
        "model": LLM_MODEL,                                                                                                                                                                                         
        "prompt": prompt,                                                                                                                                                                                           
        "stream": False,                                                                                                                                                                                            
        "options": {                                                                                                                                                                                                
            "temperature": temperature,                                                                                                                                                                             
            "num_ctx": 4096,                                                                                                                                                                                        
        },                                                                                                                                                                                                          
    }).encode("utf-8")                                                                                                                                                                                              
                                                                                                                                                                                                                    
    request = urllib.request.Request(                                                                                                                                                                               
        OLLAMA_URL,                                                                                                                                                                                                 
        data=payload,                                                                                                                                                                                               
        headers={"Content-Type": "application/json"},                                                                                                                                                               
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    with urllib.request.urlopen(request, timeout=300) as response:                                                                                                                                                  
        result = json.loads(response.read())                                                                                                                                                                        
        return result["response"]                                                                                                                                                                                   
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def get_embedding(text):                                                                                                                                                                                            
    """Get embedding from Ollama."""                                                                                                                                                                                
    payload = json.dumps({                                                                                                                                                                                          
        "model": EMBED_MODEL,                                                                                                                                                                                       
        "prompt": text,                                                                                                                                                                                             
    }).encode("utf-8")                                                                                                                                                                                              
                                                                                                                                                                                                                    
    request = urllib.request.Request(                                                                                                                                                                               
        OLLAMA_EMBED_URL,                                                                                                                                                                                           
        data=payload,                                                                                                                                                                                               
        headers={"Content-Type": "application/json"},                                                                                                                                                               
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    with urllib.request.urlopen(request) as response:                                                                                                                                                               
        result = json.loads(response.read())
        return result["embedding"]                                                                                                                                                                                  
                
                                                                                                                                                                                                                    
def get_collection():
    client = chromadb.PersistentClient(path="data/chromadb")                                                                                                                                                        
    return client.get_collection("integrable_systems")                                                                                                                                                              
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def retrieve_chunks(collection, query, top_k=TOP_K_CHUNKS, where_filter=None):                                                                                                                                      
    """Retrieve most relevant chunks for a query."""                                                                                                                                                                
    query_embedding = get_embedding(query)                                                                                                                                                                          
                                                                                                                                                                                                                    
    kwargs = {                                                                                                                                                                                                      
        "query_embeddings": [query_embedding],                                                                                                                                                                      
        "n_results": top_k,                                                                                                                                                                                         
        "include": ["documents", "metadatas", "distances"],                                                                                                                                                         
    }                                                                                                                                                                                                               
    if where_filter:                                                                                                                                                                                                
        kwargs["where"] = where_filter                                                                                                                                                                              
                                                                                                                                                                                                                    
    results = collection.query(**kwargs)                                                                                                                                                                            
                                                                                                                                                                                                                    
    chunks = []                                                                                                                                                                                                     
    for i in range(len(results["ids"][0])):
        chunks.append({                                                                                                                                                                                             
            "id": results["ids"][0][i],                                                                                                                                                                             
            "content": results["documents"][0][i],                                                                                                                                                                  
            "metadata": results["metadatas"][0][i],                                                                                                                                                                 
            "distance": results["distances"][0][i],                                                                                                                                                                 
        })                                                                                                                                                                                                          
                                                                                                                                                                                                                    
    return chunks                                                                                                                                                                                                   
                
                                                                                                                                                                                                                    
def get_style_examples(collection):
    """Retrieve all chunks from the user's own papers."""                                                                                                                                                           
    results = collection.get(                                                                                                                                                                                       
        where={"is_style_paper": True},                                                                                                                                                                             
        include=["documents", "metadatas"],                                                                                                                                                                         
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    if not results["ids"]:                                                                                                                                                                                          
        return ""
                                                                                                                                                                                                                    
    # Combine style chunks, truncate to budget                                                                                                                                                                      
    style_text = ""                                                                                                                                                                                                 
    for doc in results["documents"]:                                                                                                                                                                                
        if len(style_text) + len(doc) > MAX_STYLE_CHARS:                                                                                                                                                            
            break                                                                                                                                                                                                   
        style_text += doc + "\n\n"                                                                                                                                                                                  
                                                                                                                                                                                                                    
    return style_text.strip()                                                                                                                                                                                       
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def generate_outline(topic, collection):
    """Generate a review paper outline based on the corpus."""                                                                                                                                                      
    # Retrieve broadly relevant chunks                                                                                                                                                                              
    chunks = retrieve_chunks(collection, topic, top_k=8)                                                                                                                                                            
                                                                                                                                                                                                                    
    corpus_context = "\n\n".join(                                                                                                                                                                                   
        f"[{c['metadata'].get('title', '')}]\n{c['content'][:300]}"                                                                                                                                                 
        for c in chunks                                                                                                                                                                                             
    )[:MAX_CONTEXT_CHARS]
                                                                                                                                                                                                                    
    prompt = f"""You are a mathematical physicist writing a review paper.                                                                                                                                           
                                                                                                                                                                                                                    
Topic: {topic}                                                                                                                                                                                                      
                
Here are excerpts from relevant papers in the literature:                                                                                                                                                           
                
{corpus_context}                                                                                                                                                                                                    
                
Based on the existing literature above, propose an outline for a review paper on "{topic}".                                                                                                                         
Return ONLY the outline as a numbered list of section titles.
Include an Introduction and Conclusion.                                                                                                                                                                             
Keep it to 5-8 sections.                                                                                                                                                                                            
                                                                                                                                                                                                                    
Outline:"""                                                                                                                                                                                                         
                                                                                                                                                                                                                    
    print("Generating outline...")                                                                                                                                                                                  
    response = ollama_generate(prompt, temperature=0.5)
    return response.strip()                                                                                                                                                                                         
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def parse_outline(outline_text):                                                                                                                                                                                    
    """Extract section titles from the generated outline."""                                                                                                                                                        
    sections = []                                                                                                                                                                                                   
    for line in outline_text.split("\n"):                                                                                                                                                                           
        line = line.strip()                                                                                                                                                                                         
        # Match numbered lines: "1. Title" or "1) Title"                                                                                                                                                            
        match = re.match(r"^\d+[\.\)]\s*(.+)", line)                                                                                                                                                                
        if match:                                                                                                                                                                                                   
            sections.append(match.group(1).strip())                                                                                                                                                                 
                                                                                                                                                                                                                    
    if not sections:                                                                                                                                                                                                
        # Fallback: treat each non-empty line as a section                                                                                                                                                          
        sections = [line.strip() for line in outline_text.split("\n") if line.strip()]                                                                                                                              
                                                                                                                                                                                                                    
    return sections                                                                                                                                                                                                 
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def generate_section(section_title, topic, collection, style_text, previous_sections):
    """Generate one section of the review paper."""                                                                                                                                                                 
                                                                                                                                                                                                                    
    # Retrieve chunks relevant to this specific section                                                                                                                                                             
    query = f"{topic}: {section_title}"                                                                                                                                                                             
    chunks = retrieve_chunks(collection, query, top_k=TOP_K_CHUNKS)                                                                                                                                                 
                                                                                                                                                                                                                    
    # Build source context                                                                                                                                                                                          
    source_context = "\n\n".join(                                                                                                                                                                                   
        f"[Source: {c['metadata'].get('title', 'unknown')}]\n{c['content']}"                                                                                                                                        
        for c in chunks                                                                                                                                                                                             
    )[:MAX_CONTEXT_CHARS]                                                                                                                                                                                           
                                                                                                                                                                                                                    
    # Build list of papers cited for bibliography                                                                                                                                                                   
    cited_papers = list({                                                                                                                                                                                           
        c["metadata"].get("title", "") for c in chunks if c["metadata"].get("title")                                                                                                                                
    })                                                                                                                                                                                                              
                                                                                                                                                                                                                    
    # Context from previously generated sections (continuity)                                                                                                                                                       
    prev_context = ""
    if previous_sections:                                                                                                                                                                                           
        last_section = previous_sections[-1]                                                                                                                                                                        
        prev_context = f"\nThe previous section was:\n{last_section['content'][:500]}\n"                                                                                                                            
                                                                                                                                                                                                                    
    # Style guidance                                                                                                                                                                                                
    style_block = ""                                                                                                                                                                                                
    if style_text:                                                                                                                                                                                                  
        style_block = f"""                                                                                                                                                                                          
Write in the same style as this author. Match their tone, notation, and level of detail:                                                                                                                            
                                                                                                                                                                                                                    
{style_text[:MAX_STYLE_CHARS]}                                                                                                                                                                                      
"""                                                                                                                                                                                                                 
                                                                                                                                                                                                                    
    prompt = f"""You are a mathematical physicist writing a review paper on "{topic}".                                                                                                                              
{style_block}
You are now writing the section: "{section_title}"                                                                                                                                                                  
{prev_context}                                                                                                                                                                                                      
Use the following source material to inform this section:                                                                                                                                                           
                                                                                                                                                                                                                    
{source_context}                                                                                                                                                                                                    
                                                                                                                                                                                                                    
Write this section in LaTeX. Include:                                                                                                                                                                               
- A \\subsection{{}} heading
- Mathematical equations in equation/align environments where appropriate                                                                                                                                           
- References to the source papers where relevant (use \\cite{{}} placeholders)                                                                                                                                      
- Clear exposition connecting the mathematical ideas                                                                                                                                                                
                                                                                                                                                                                                                    
Write ONLY the LaTeX content for this section, nothing else.                                                                                                                                                        
                                                                                                                                                                                                                    
\\subsection{{{section_title}}}"""                                                                                                                                                                                  
                
    print(f"  Generating: {section_title}...")                                                                                                                                                                      
    content = ollama_generate(prompt, temperature=0.7)
                                                                                                                                                                                                                    
    return {                                                                                                                                                                                                        
        "title": section_title,                                                                                                                                                                                     
        "content": f"\\subsection{{{section_title}}}\n{content}",                                                                                                                                                   
        "cited_papers": cited_papers,                                                                                                                                                                               
    }                                                                                                                                                                                                               
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def assemble_paper(topic, sections, author_name=""):                                                                                                                                                                
    """Assemble generated sections into a complete LaTeX document."""                                                                                                                                               
    today = date.today().strftime("%B %Y")                                                                                                                                                                          
                                                                                                                                                                                                                    
    # Collect all cited papers                                                                                                                                                                                      
    all_cited = []                                                                                                                                                                                                  
    for section in sections:                                                                                                                                                                                        
        all_cited.extend(section.get("cited_papers", []))                                                                                                                                                           
    unique_cited = list(dict.fromkeys(all_cited))  # preserve order, deduplicate                                                                                                                                    
                                                                                                                                                                                                                    
    # Build bibliography entries                                                                                                                                                                                    
    bib_entries = []                                                                                                                                                                                                
    for i, title in enumerate(unique_cited, 1):                                                                                                                                                                     
        key = f"ref{i}"                                                                                                                                                                                             
        bib_entries.append(f"\\bibitem{{{key}}} {title}.")                                                                                                                                                          
                                                                                                                                                                                                                    
    bib_block = "\n".join(bib_entries) if bib_entries else "\\bibitem{ref1} [References to be completed]."                                                                                                          
                                                                                                                                                                                                                    
    # Assemble sections                                                                                                                                                                                             
    body = "\n\n".join(section["content"] for section in sections)
                                                                                                                                                                                                                    
    latex = f"""\\documentclass[12pt]{{article}}                                                                                                                                                                    
                                                                                                                                                                                                                    
\\usepackage{{amsmath, amssymb, amsthm}}                                                                                                                                                                            
\\usepackage{{mathrsfs}}
\\usepackage{{geometry}}                                                                                                                                                                                            
\\geometry{{margin=1in}}                                                                                                                                                                                            
                                                                                                                                                                                                                    
\\newtheorem{{theorem}}{{Theorem}}[section]                                                                                                                                                                         
\\newtheorem{{lemma}}[theorem]{{Lemma}}                                                                                                                                                                             
\\newtheorem{{proposition}}[theorem]{{Proposition}}                                                                                                                                                                 
\\newtheorem{{corollary}}[theorem]{{Corollary}}                                                                                                                                                                     
\\newtheorem{{definition}}[theorem]{{Definition}}                                                                                                                                                                   
\\newtheorem{{remark}}[theorem]{{Remark}}                                                                                                                                                                           
\\newtheorem{{example}}[theorem]{{Example}}                                                                                                                                                                         
                                                                                                                                                                                                                    
\\title{{A Review of {topic}}}                                                                                                                                                                                      
\\author{{{author_name}}}                                                                                                                                                                                           
\\date{{{today}}}                                                                                                                                                                                                   
                                                                                                                                                                                                                    
\\begin{{document}}                                                                                                                                                                                                 
                                                                                                                                                                                                                    
\\maketitle                                                                                                                                                                                                         
                
\\begin{{abstract}}                                                                                                                                                                                                 
This paper provides a review of {topic.lower()}, surveying the key results,
methods, and open problems in the field. [Abstract to be refined.]                                                                                                                                                  
\\end{{abstract}}                                                                                                                                                                                                   
                                                                                                                                                                                                                    
\\tableofcontents                                                                                                                                                                                                   
                
# \\section{{Introduction}} -- Removed, as the LLM is prompted to include it in the outline
                
{body}                                                                                                                                                                                                              
                
\\begin{{thebibliography}}{{99}}                                                                                                                                                                                    
{bib_block}     
\\end{{thebibliography}}                                                                                                                                                                                            
                                                                                                                                                                                                                    
\\end{{document}}                                                                                                                                                                                                   
"""                                                                                                                                                                                                                 
    return latex                                                                                                                                                                                                    
                
                                                                                                                                                                                                                    
def main():     
    parser = argparse.ArgumentParser(                                                                                                                                                                               
        description="Generate a review paper via RAG"                                                                                                                                                               
    )                                                                                                                                                                                                               
    parser.add_argument(                                                                                                                                                                                            
        "--topic", type=str, required=True,                                                                                                                                                                         
        help="Review paper topic",                                                                                                                                                                                  
    )                                                                                                                                                                                                               
    parser.add_argument(                                                                                                                                                                                            
        "--sections", type=int, default=6,                                                                                                                                                                          
        help="Target number of sections (default: 6)",                                                                                                                                                              
    )                                                                                                                                                                                                               
    parser.add_argument(                                                                                                                                                                                            
        "--author", type=str, default="",                                                                                                                                                                           
        help="Author name for the paper",                                                                                                                                                                           
    )                                                                                                                                                                                                               
    parser.add_argument(                                                                                                                                                                                            
        "--outline-only", action="store_true",                                                                                                                                                                      
        help="Generate and display outline without writing sections",                                                                                                                                               
    )                                                                                                                                                                                                               
    args = parser.parse_args()                                                                                                                                                                                      
                                                                                                                                                                                                                    
    collection = get_collection()                                                                                                                                                                                   
                                                                                                                                                                                                                    
    if collection.count() == 0:                                                                                                                                                                                     
        print("No embeddings found. Run 03_embed_store.py first.")
        return                                                                                                                                                                                                      
                                                                                                                                                                                                                    
    # Get style examples from your papers                                                                                                                                                                           
    style_text = get_style_examples(collection)                                                                                                                                                                     
    if style_text:                                                                                                                                                                                                  
        print(f"Loaded style reference ({len(style_text)} chars)")                                                                                                                                                  
    else:                                                                                                                                                                                                           
        print("No style papers found — generating without style matching")                                                                                                                                          
                                                                                                                                                                                                                    
    # Step 1: Generate outline                                                                                                                                                                                      
    outline_raw = generate_outline(args.topic, collection)                                                                                                                                                          
    section_titles = parse_outline(outline_raw)                                                                                                                                                                     
                                                                                                                                                                                                                    
    # Trim to requested section count                                                                                                                                                                               
    if len(section_titles) > args.sections:                                                                                                                                                                         
        section_titles = section_titles[:args.sections]                                                                                                                                                             
                                                                                                                                                                                                                    
    print(f"\nProposed outline ({len(section_titles)} sections):")                                                                                                                                                  
    for i, title in enumerate(section_titles, 1):                                                                                                                                                                   
        print(f"  {i}. {title}")                                                                                                                                                                                    
                                                                                                                                                                                                                    
    if args.outline_only:                                                                                                                                                                                           
        return                                                                                                                                                                                                      
                                                                                                                                                                                                                    
    print(f"\nGenerating paper...\n")                                                                                                                                                                               
                                                                                                                                                                                                                    
    # Step 2: Generate each section                                                                                                                                                                                 
    generated_sections = []
    for title in section_titles:                                                                                                                                                                                    
        section = generate_section(                                                                                                                                                                                 
            title, args.topic, collection,                                                                                                                                                                          
            style_text, generated_sections,                                                                                                                                                                         
        )                                                                                                                                                                                                           
        generated_sections.append(section)                                                                                                                                                                          
        print(f"    Done ({len(section['content'])} chars)")                                                                                                                                                        
                                                                                                                                                                                                                    
    # Step 3: Assemble into LaTeX                                                                                                                                                                                   
    latex = assemble_paper(args.topic, generated_sections, author_name=args.author)                                                                                                                                 
                                                                                                                                                                                                                    
    # Save                                                                                                                                                                                                          
    output_dir = Path("output")                                                                                                                                                                                     
    output_dir.mkdir(exist_ok=True)                                                                                                                                                                                 
                                                                                                                                                                                                                    
    safe_topic = re.sub(r"[^a-zA-Z0-9]+", "_", args.topic)[:50]                                                                                                                                                     
    output_path = output_dir / f"review_{safe_topic}.tex"                                                                                                                                                           
                                                                                                                                                                                                                    
    output_path.write_text(latex)                                                                                                                                                                                   
    print(f"\n{'=' * 50}")                                                                                                                                                                                          
    print(f"Paper saved to: {output_path}")                                                                                                                                                                         
    print(f"Sections: {len(generated_sections)}")                                                                                                                                                                   
    print(f"\nNext steps:")                                                                                                                                                                                         
    print(f"  1. Review and edit the generated LaTeX")                                                                                                                                                              
    print(f"  2. Fix \\cite{{}} placeholders with real references")                                                                                                                                                 
    print(f"  3. Refine the abstract")                                                                                                                                                                              
    print(f"  4. Compile: pdflatex {output_path}")                                                                                                                                                                  
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
if __name__ == "__main__":                                                                                                                                                                                          
    main()  