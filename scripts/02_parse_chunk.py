import argparse
import json
import re
from pathlib import Path

import yaml

def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)

# Figures & tables?
THEOREM_ENVS = {"theorem", "lemma", "proposition", "corollary", "definition", "remark", "example", "conjecture", "proof",}

# ~ 400-500 tokens for embedding models?
MAX_CHUNK_CHARS = 2000
MIN_CHUNK_CHARS = 100


# Remove LaTeX comments (lines starting with % or inline %).
def strip_comments(text):
    # Remove comments while ignoring escaped percent signs \%
    # This regex looks for % not preceded by \
    text = re.sub(r"(?<!\\)%.*", "", text)
    return text


# Extract body between \\begin{document} and \\end{document}
def extract_body(text):
    match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


# Extract \\newcommand & \\DeclareMathOperator defs.
def extract_preamble_commands(text):
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


# Split document body into sections/subsections.
def split_sections(body):
    pattern = r"(\\(?:sub)*section\*?\{[^}]*\})"
    parts = re.split(pattern, body)
    
    sections = []

    if parts[0].strip():
          sections.append(("preamble", parts[0].strip()))
 
    # Pair headings with their content
    for i in range(1, len(parts), 2):
        heading = parts[i]
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        title_match = re.search(r"\{([^}]*)\}", heading)
        title = title_match.group(1) if title_match else heading
        sections.append((title, f"{heading}\n{content}"))
    return sections


# Split text on theorem-like environments, keeping each as a separate chunk.
def split_environments(text):
    env_names = "|".join(THEOREM_ENVS)
    pattern = rf"(\\begin\{{({env_names})\}}.*?\\end\{{\2\}})"

    chunks = []
    last_end = 0

    for match in re.finditer(pattern, text, re.DOTALL):
        # Text before this environment
        before = text[last_end:match.start()].strip()
        if before:
            chunks.append(("text", before))

        env_name = match.group(2)
        chunks.append((env_name, match.group(1)))
        last_end = match.end()

    # Remaining text after last environment
    remaining = text[last_end:].strip()
    if remaining:
        chunks.append(("text", remaining))

    return chunks


# Split oversized chunks on paragraph breaks (double newline).
def split_long_chunk(text, max_chars=MAX_CHUNK_CHARS):
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



def find_main_tex(paper_dir):
    """Find the main .tex file in a paper directory.

    Looks for \\begin{document} to identify the root file.
    Falls back to main.tex or the largest .tex file.
    """
    tex_files = list(Path(paper_dir).glob("**/*.tex"))

    if not tex_files:
        return None

    if len(tex_files) == 1:
        return tex_files[0]
 
      # Look for the file containing \begin{document}
    for tex_file in tex_files:
        try:
            content = tex_file.read_text(errors="ignore")
            if r"\begin{document}" in content:
                return tex_file
        except Exception:
            continue
    
        # Fallback: main.tex or paper.tex
        for name in ["main.tex", "paper.tex", "article.tex"]:
            candidate = Path(paper_dir) / name
            if candidate.exists():
                return candidate

        # Last resort: largest file
        return max(tex_files, key=lambda f: f.stat().st_size)
    


def resolve_inputs(text, paper_dir):
    """Resolve \\input{filename} and \\include{filename} directives."""
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


# Process one paper into chunks. Returns list of chunk dicts ready for embedding.
def chunk_paper(paper_dir, metadata, is_style_paper=False):

    main_tex = find_main_tex(paper_dir)
    if main_tex is None:
        return []

    try:
        raw_text = main_tex.read_text(errors="ignore")
    except Exception:
        return []

    # Resolve \input{} references
    raw_text = resolve_inputs(raw_text, paper_dir)

    # Extract custom commands (notation context)
    custom_commands = extract_preamble_commands(raw_text)

    # Clean and extract body
    text = strip_comments(raw_text)
    body = extract_body(text)

    if len(body) < MIN_CHUNK_CHARS:
        return []

    # Split into sections
    sections = split_sections(body)

    chunks = []
    chunk_index = 0

    for section_title, section_content in sections:
        # Split each section on theorem environments
        env_chunks = split_environments(section_content)

        for chunk_type, chunk_text in env_chunks:
            # Further split if too long
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
                    "custom_commands": custom_commands,
                    "is_style_paper": is_style_paper,
                    "citation_key": generate_citation_key(metadata), # Add a suggested citation key
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

# Process all downloaded arXiv papers.
def process_arxiv_papers(config):
    metadata_dir = Path(config["paths"]["metadata"])
    manifest_path = metadata_dir / "manifest.json"

    if not manifest_path.exists():
        print("No manifest found. Run 01_fetch_arxiv.py first.")
        return []

    with open(manifest_path) as f:
        papers = json.load(f)

    all_chunks = []

    for paper in papers:
        paper_dir = Path(paper["source_dir"])
        if not paper_dir.exists():
            continue

        chunks = chunk_paper(paper_dir, paper, is_style_paper=False)
        all_chunks.extend(chunks)
        print(f"  {paper['arxiv_id']}: {len(chunks)} chunks")

    return all_chunks


### Process your own papers (style references).
def process_style_papers(style_dir):
    style_path = Path(style_dir)
    if not style_path.exists():
        print(f"Style directory {style_dir} not found, skipping.")
        return []

    all_chunks = []

    for tex_file in style_path.glob("**/*.tex"):
        paper_dir = tex_file.parent
        metadata = {
            "arxiv_id": f"style_{tex_file.stem}",
            "title": tex_file.stem,
            "authors": ["self"],
        }
        chunks = chunk_paper(paper_dir, metadata, is_style_paper=True)
        all_chunks.extend(chunks)
        print(f"  [STYLE] {tex_file.name}: {len(chunks)} chunks")

    return all_chunks
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Parse LaTeX papers into chunks for embedding"
    )
    parser.add_argument(
        "--style", type=str, default="style_papers",
        help="Directory containing your own papers (default: style_papers/)",
    )
    args = parser.parse_args()

    config = load_config()
    chunks_dir = Path("data/chunks")
    chunks_dir.mkdir(parents=True, exist_ok=True)

    print("Processing arXiv papers...")
    arxiv_chunks = process_arxiv_papers(config)

    print(f"\nProcessing style papers from {args.style}...")
    style_chunks = process_style_papers(args.style)

    all_chunks = arxiv_chunks + style_chunks

    # Save all chunks
    output_path = chunks_dir / "all_chunks.json"
    with open(output_path, "w") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 50}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"  arXiv:  {len(arxiv_chunks)}")
    print(f"  Style:  {len(style_chunks)}")
    print(f"Saved to: {output_path}")
 
 
if __name__ == "__main__":
    main()
