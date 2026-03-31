import re                                                                                                                                                                                                           
from pathlib import Path
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
THEOREM_ENVS = {                                                                                                                                                                                                    
    "theorem", "lemma", "proposition", "corollary",                                                                                                                                                                 
    "definition", "remark", "example", "conjecture",                                                                                                                                                                
    "proof",                                                                                                                                                                                                        
}                                                                                                                                                                                                                   
                                                                                                                                                                                                                    
MAX_CHUNK_CHARS = 2000                                                                                                                                                                                              
MIN_CHUNK_CHARS = 100                                                                                                                                                                                               
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def find_main_tex(paper_dir):                                                                                                                                                                                       
    """Find the root .tex file in a paper directory."""                                                                                                                                                             
    tex_files = list(Path(paper_dir).rglob("*.tex"))                                                                                                                                                                
                                                                                                                                                                                                                    
    if not tex_files:                                                                                                                                                                                               
        return None                                                                                                                                                                                                 
                                                                                                                                                                                                                    
    if len(tex_files) == 1:                                                                                                                                                                                         
        return tex_files[0]                                                                                                                                                                                         
                                                                                                                                                                                                                    
    for tex_file in tex_files:                                                                                                                                                                                      
        try:                                                                                                                                                                                                        
            content = tex_file.read_text(errors="ignore")                                                                                                                                                           
            if r"\begin{document}" in content:                                                                                                                                                                      
                return tex_file                                                                                                                                                                                     
        except Exception:                                                                                                                                                                                           
            continue                                                                                                                                                                                                
                
    for name in ["main.tex", "paper.tex", "article.tex"]:                                                                                                                                                           
        candidate = Path(paper_dir) / name
        if candidate.exists():                                                                                                                                                                                      
            return candidate
                                                                                                                                                                                                                    
    return max(tex_files, key=lambda f: f.stat().st_size)                                                                                                                                                           
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def resolve_inputs(text, paper_dir):
    """Resolve \\input{} and \\include{} directives."""                                                                                                                                                             
    def replacer(match):                                                                                                                                                                                            
        filename = match.group(1)                                                                                                                                                                                   
        if not filename.endswith(".tex"):                                                                                                                                                                           
            filename += ".tex"                                                                                                                                                                                      
        input_path = Path(paper_dir) / filename                                                                                                                                                                     
        if input_path.exists():                                                                                                                                                                                     
            try:                                                                                                                                                                                                    
                return input_path.read_text(errors="ignore")                                                                                                                                                        
            except Exception:                                                                                                                                                                                       
                return match.group(0)                                                                                                                                                                               
        return match.group(0)                                                                                                                                                                                       
                                                                                                                                                                                                                    
    text = re.sub(r"\\input\{([^}]+)\}", replacer, text)                                                                                                                                                            
    text = re.sub(r"\\include\{([^}]+)\}", replacer, text)                                                                                                                                                          
    return text                                                                                                                                                                                                     
                
                                                                                                                                                                                                                    
def strip_comments(text):
    """Remove LaTeX comments."""                                                                                                                                                                                    
    lines = text.split("\n")                                                                                                                                                                                        
    cleaned = [re.sub(r"(?<!\\)%.*", "", line) for line in lines]                                                                                                                                                   
    return "\n".join(cleaned)                                                                                                                                                                                       
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def extract_body(text):                                                                                                                                                                                             
    """Extract content between \\begin{document} and \\end{document}."""                                                                                                                                            
    match = re.search(                                                                                                                                                                                              
        r"\\begin\{document\}(.*?)\\end\{document\}",                                                                                                                                                               
        text,                                                                                                                                                                                                       
        re.DOTALL,                                                                                                                                                                                                  
    )                                                                                                                                                                                                               
    return match.group(1).strip() if match else text.strip()                                                                                                                                                        
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def extract_preamble_commands(text):                                                                                                                                                                                
    """Extract \\newcommand and \\DeclareMathOperator definitions."""                                                                                                                                               
    match = re.search(r"^(.*?)\\begin\{document\}", text, re.DOTALL)                                                                                                                                                
    if not match:                                                                                                                                                                                                   
        return ""                                                                                                                                                                                                   
                                                                                                                                                                                                                    
    preamble = match.group(1)                                                                                                                                                                                       
    commands = []                                                                                                                                                                                                   
    for pattern in [                                                                                                                                                                                                
        r"\\(?:re)?newcommand\{[^}]+\}(?:\[\d+\])?\{[^}]*\}",                                                                                                                                                       
        r"\\DeclareMathOperator\*?\{[^}]+\}\{[^}]+\}",                                                                                                                                                              
        r"\\def\\[a-zA-Z]+\{[^}]*\}",                                                                                                                                                                               
    ]:                                                                                                                                                                                                              
        commands.extend(re.findall(pattern, preamble))                                                                                                                                                              
                                                                                                                                                                                                                    
    return "\n".join(commands) if commands else ""                                                                                                                                                                  
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def split_sections(body):
    """Split document body into (heading, content) pairs."""                                                                                                                                                        
    pattern = r"(\\(?:sub)*section\*?\{[^}]*\})"                                                                                                                                                                    
    parts = re.split(pattern, body)                                                                                                                                                                                 
                                                                                                                                                                                                                    
    sections = []                                                                                                                                                                                                   
                                                                                                                                                                                                                    
    if parts[0].strip():                                                                                                                                                                                            
        sections.append(("preamble", parts[0].strip()))
                                                                                                                                                                                                                    
    for i in range(1, len(parts), 2):                                                                                                                                                                               
        heading = parts[i]                                                                                                                                                                                          
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""                                                                                                                                                
        title_match = re.search(r"\{([^}]*)\}", heading)                                                                                                                                                            
        title = title_match.group(1) if title_match else heading                                                                                                                                                    
        sections.append((title, f"{heading}\n{content}"))                                                                                                                                                           
                                                                                                                                                                                                                    
    return sections                                                                                                                                                                                                 
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def split_environments(text):
    """Split text on theorem-like environments."""                                                                                                                                                                  
    env_names = "|".join(THEOREM_ENVS)                                                                                                                                                                              
    pattern = rf"(\\begin\{{({env_names})\}}.*?\\end\{{\2\}})"                                                                                                                                                      
                                                                                                                                                                                                                    
    chunks = []                                                                                                                                                                                                     
    last_end = 0                                                                                                                                                                                                    
                                                                                                                                                                                                                    
    for match in re.finditer(pattern, text, re.DOTALL):                                                                                                                                                             
        before = text[last_end:match.start()].strip()                                                                                                                                                               
        if before:                                                                                                                                                                                                  
            chunks.append(("text", before))                                                                                                                                                                         
        chunks.append((match.group(2), match.group(1)))                                                                                                                                                             
        last_end = match.end()                                                                                                                                                                                      
                                                                                                                                                                                                                    
    remaining = text[last_end:].strip()                                                                                                                                                                             
    if remaining:                                                                                                                                                                                                   
        chunks.append(("text", remaining))                                                                                                                                                                          
                                                                                                                                                                                                                    
    return chunks                                                                                                                                                                                                   
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def split_long_chunk(text, max_chars=MAX_CHUNK_CHARS):
    """Split oversized chunks on paragraph breaks."""                                                                                                                                                               
    if len(text) <= max_chars:                                                                                                                                                                                      
        return [text]                                                                                                                                                                                               
                                                                                                                                                                                                                    
    paragraphs = re.split(r"\n\s*\n", text)                                                                                                                                                                         
    chunks = [] 
    current = ""                                                                                                                                                                                                    
                                                                                                                                                                                                                    
    for paragraph in paragraphs:                                                                                                                                                                                    
        if len(current) + len(paragraph) > max_chars and current:                                                                                                                                                   
            chunks.append(current.strip())                                                                                                                                                                          
            current = paragraph                                                                                                                                                                                     
        else:                                                                                                                                                                                                       
            current = current + "\n\n" + paragraph if current else paragraph                                                                                                                                        
                                                                                                                                                                                                                    
    if current.strip():                                                                                                                                                                                             
        chunks.append(current.strip())                                                                                                                                                                              
                                                                                                                                                                                                                    
    return chunks                                                                                                                                                                                                   
                                                                                                                                                                                                                    
