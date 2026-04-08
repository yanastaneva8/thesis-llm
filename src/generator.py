import re                                                                                                                                                                                                           
from datetime import date                                                                                                                                                                                           
from pathlib import Path                                                                                                                                                                                            
                                                                                                                                                                                                                    
from src.config import OUTPUT_DIR                                                                                                                                                                                   
from src.ollama_client import generate                                                                                                                                                                              
from src.retriever import retrieve, get_style_examples, build_source_context, MAX_STYLE_CHARS                                                                                                                       
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def generate_outline(topic):                                                                                                                                                                                        
    """Generate a review paper outline from the corpus."""                                                                                                                                                          
    chunks = retrieve(topic, top_k=8)                                                                                                                                                                               
    corpus_context = build_source_context(chunks)                                                                                                                                                                   
                                                                                                                                                                                                                    
    prompt = f"""You are a mathematical physicist writing a review paper.                                                                                                                                           
                                                                                                                                                                                                                    
Topic: {topic}                                                                                                                                                                                                      
                
Here are excerpts from relevant papers in the literature:                                                                                                                                                           
                
{corpus_context}                                                                                                                                                                                                    
                
Based on the existing literature above, propose an outline for a review paper on "{topic}".                                                                                                                         
Return ONLY the outline as a numbered list of section titles.
Include an Introduction and Conclusion.                                                                                                                                                                             
Keep it to 5-8 sections.                                                                                                                                                                                            
                                                                                                                                                                                                                    
Outline:"""                                                                                                                                                                                                         
                                                                                                                                                                                                                    
    response = generate(prompt, temperature=0.5)                                                                                                                                                                    
    return parse_outline(response)
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def parse_outline(outline_text):                                                                                                                                                                                    
    """Extract section titles from generated outline."""                                                                                                                                                            
    sections = []                                                                                                                                                                                                   
    for line in outline_text.strip().split("\n"):                                                                                                                                                                   
        match = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())                                                                                                                                                        
        if match:                                                                                                                                                                                                   
            sections.append(match.group(1).strip())                                                                                                                                                                 
                                                                                                                                                                                                                    
    if not sections:                                                                                                                                                                                                
        sections = [line.strip() for line in outline_text.split("\n") if line.strip()]                                                                                                                              
                                                                                                                                                                                                                    
    return sections                                                                                                                                                                                                 
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def generate_section(section_title, topic, style_text, previous_sections):
    """Generate one section of the review paper."""                                                                                                                                                                 
    chunks = retrieve(f"{topic}: {section_title}", top_k=4)                                                                                                                                                         
    source_context = build_source_context(chunks)                                                                                                                                                                   
                                                                                                                                                                                                                    
    cited_papers = list({                                                                                                                                                                                           
        chunk["metadata"].get("title", "")                                                                                                                                                                          
        for chunk in chunks if chunk["metadata"].get("title")                                                                                                                                                       
    })                                                                                                                                                                                                              
                                                                                                                                                                                                                    
    previous_context = ""                                                                                                                                                                                           
    if previous_sections:
        last = previous_sections[-1]                                                                                                                                                                                
        previous_context = f"\nThe previous section was:\n{last['content'][:500]}\n"                                                                                                                                
                                                                                                                                                                                                                    
    style_block = ""                                                                                                                                                                                                
    if style_text:                                                                                                                                                                                                  
        style_block = f"""                                                                                                                                                                                          
Write in the same style as this author. Match their tone, notation, and level of detail:                                                                                                                            
                                                                                                                                                                                                                    
{style_text[:MAX_STYLE_CHARS]}                                                                                                                                                                                      
"""                                                                                                                                                                                                                 
                                                                                                                                                                                                                    
    prompt = f"""You are a mathematical physicist writing a review paper on "{topic}".                                                                                                                              
{style_block}
You are now writing the section: "{section_title}"                                                                                                                                                                  
{previous_context}                                                                                                                                                                                                  
Use the following source material to inform this section:                                                                                                                                                           
                                                                                                                                                                                                                    
{source_context}                                                                                                                                                                                                    
                                                                                                                                                                                                                    
Write this section in LaTeX. Include:                                                                                                                                                                               
- A \\subsection{{}} heading
- Mathematical equations in equation/align environments where appropriate                                                                                                                                           
- References to the source papers where relevant (use \\cite{{}} placeholders)                                                                                                                                      
- Clear exposition connecting the mathematical ideas                                                                                                                                                                
                                                                                                                                                                                                                    
Write ONLY the LaTeX content for this section, nothing else.                                                                                                                                                        
                                                                                                                                                                                                                    
\\subsection{{{section_title}}}"""                                                                                                                                                                                  
                
    content = generate(prompt, temperature=0.7)                                                                                                                                                                     
                
    return {                                                                                                                                                                                                        
        "title": section_title,
        "content": f"\\subsection{{{section_title}}}\n{content}",                                                                                                                                                   
        "cited_papers": cited_papers,                                                                                                                                                                               
    }                                                                                                                                                                                                               
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def assemble_paper(topic, sections, author_name=""):                                                                                                                                                                
    """Assemble sections into a complete LaTeX document."""                                                                                                                                                         
    today = date.today().strftime("%B %Y")                                                                                                                                                                          
                                                                                                                                                                                                                    
    all_cited = []                                                                                                                                                                                                  
    for section in sections:                                                                                                                                                                                        
        all_cited.extend(section.get("cited_papers", []))                                                                                                                                                           
    unique_cited = list(dict.fromkeys(all_cited))                                                                                                                                                                   
                                                                                                                                                                                                                    
    bib_entries = "\n".join(                                                                                                                                                                                        
        f"\\bibitem{{ref{i}}} {title}."                                                                                                                                                                             
        for i, title in enumerate(unique_cited, 1)                                                                                                                                                                  
    ) or "\\bibitem{ref1} [References to be completed]."                                                                                                                                                            
                                                                                                                                                                                                                    
    body = "\n\n".join(section["content"] for section in sections)                                                                                                                                                  
                                                                                                                                                                                                                    
    return f"""\\documentclass[12pt]{{article}}                                                                                                                                                                     
                
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
{bib_entries}   
\\end{{thebibliography}}                                                                                                                                                                                            
                                                                                                                                                                                                                    
\\end{{document}}                                                                                                                                                                                                   
"""                                                                                                                                                                                                                 
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def generate_paper(topic, num_sections=6, author_name=""):                                                                                                                                                          
    """Full pipeline: outline → sections → assembled LaTeX."""                                                                                                                                                      
    OUTPUT_DIR.mkdir(exist_ok=True)                                                                                                                                                                                 
                                                                                                                                                                                                                    
    style_text = get_style_examples()                                                                                                                                                                               
    if style_text:                                                                                                                                                                                                  
        print(f"Style reference loaded ({len(style_text)} chars)")                                                                                                                                                  
    else:                                                                                                                                                                                                           
        print("No style papers found — generating without style matching")                                                                                                                                          
                                                                                                                                                                                                                    
    # Outline                                                                                                                                                                                                       
    print("Generating outline...")                                                                                                                                                                                  
    section_titles = generate_outline(topic)[:num_sections]                                                                                                                                                         
                                                                                                                                                                                                                    
    print(f"\nOutline ({len(section_titles)} sections):")                                                                                                                                                           
    for i, title in enumerate(section_titles, 1):                                                                                                                                                                   
        print(f"  {i}. {title}")                                                                                                                                                                                    
                                                                                                                                                                                                                    
    # Sections                                                                                                                                                                                                      
    print("\nGenerating sections...\n")                                                                                                                                                                             
    generated_sections = []                                                                                                                                                                                         
    for title in section_titles:                                                                                                                                                                                    
        print(f"  Writing: {title}...")                                                                                                                                                                             
        section = generate_section(title, topic, style_text, generated_sections)                                                                                                                                    
        generated_sections.append(section)                                                                                                                                                                          
        print(f"    Done ({len(section['content'])} chars)")                                                                                                                                                        
                                                                                                                                                                                                                    
    # Assemble                                                                                                                                                                                                      
    latex = assemble_paper(topic, generated_sections, author_name)                                                                                                                                                  
                                                                                                                                                                                                                    
    safe_topic = re.sub(r"[^a-zA-Z0-9]+", "_", topic)[:50]                                                                                                                                                          
    output_path = OUTPUT_DIR / f"review_{safe_topic}.tex"                                                                                                                                                           
    output_path.write_text(latex)                                                                                                                                                                                   
                                                                                                                                                                                                                    
    print(f"\nPaper saved to: {output_path}")                                                                                                                                                                       
    return output_path                                                                                                                                                                                              
