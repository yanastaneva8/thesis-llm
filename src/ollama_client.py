import json                                                                                                                                                                                                         
import urllib.request
                                                                                                                                                                                                                    
from src.config import OLLAMA_URL, LLM_MODEL, EMBED_MODEL                                                                                                                                                           
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def get_embedding(text):
    """Get embedding vector from Ollama."""                                                                                                                                                                         
    payload = json.dumps({                                                                                                                                                                                          
        "model": EMBED_MODEL,                                                                                                                                                                                       
        "prompt": text,                                                                                                                                                                                             
    }).encode("utf-8")                                                                                                                                                                                              
                                                                                                                                                                                                                    
    request = urllib.request.Request(                                                                                                                                                                               
        f"{OLLAMA_URL}/api/embeddings",                                                                                                                                                                             
        data=payload,                                                                                                                                                                                               
        headers={"Content-Type": "application/json"},                                                                                                                                                               
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    with urllib.request.urlopen(request) as response:                                                                                                                                                               
        result = json.loads(response.read())
        return result["embedding"]                                                                                                                                                                                  
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def generate(prompt, temperature=0.7, num_ctx=4096):                                                                                                                                                                
    """Generate text from Ollama LLM."""                                                                                                                                                                            
    payload = json.dumps({                                                                                                                                                                                          
        "model": LLM_MODEL,                                                                                                                                                                                         
        "prompt": prompt,                                                                                                                                                                                           
        "stream": False,                                                                                                                                                                                            
        "options": {                                                                                                                                                                                                
            "temperature": temperature,                                                                                                                                                                             
            "num_ctx": num_ctx,                                                                                                                                                                                     
        },                                                                                                                                                                                                          
    }).encode("utf-8")                                                                                                                                                                                              
                                                                                                                                                                                                                    
    request = urllib.request.Request(                                                                                                                                                                               
        f"{OLLAMA_URL}/api/generate",                                                                                                                                                                               
        data=payload,                                                                                                                                                                                               
        headers={"Content-Type": "application/json"},
    )                                                                                                                                                                                                               
                                                                                                                                                                                                                    
    with urllib.request.urlopen(request, timeout=300) as response:                                                                                                                                                  
        result = json.loads(response.read())                                                                                                                                                                        
        return result["response"]                                                                                                                                                                                   
                                                                                                                                                                                                                    
                                                                                                                                                                                                                    
def is_available():                                                                                                                                                                                                 
    """Check if Ollama is running."""                                                                                                                                                                               
    try:                                                                                                                                                                                                            
        get_embedding("test")
        return True                                                                                                                                                                                                 
    except Exception:
        return False                                                                                                                                                                                                
                                                                                                                                                                                                                    
