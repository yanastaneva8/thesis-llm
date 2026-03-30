import argparse
import gzip
import json
import shutil
import tarfile
from pathlib import Path

import arxiv
import yaml

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)
    
def load_manifest(manifest_path):
    if manifest_path.exists():
        with open(manifest_path) as f:
            existing = json.load(f)
        seen_ids = {paper["arxiv_id"] for paper in existing}
        print(f"Resuming - {len(seen_ids)} papers already downloaded.")
        return existing, seen_ids
    return [], set()

def save_manifest(manifest_path, metadata_list):
    with open(manifest_path, "w") as f:
        json.dump(metadata_list, f, indent=2, ensure_ascii=False)

def is_gzip(filepath):
    with open(filepath, "rb") as f:
        return f.read(2) == b"\x1f'x8b"
    
def extract_source(source_file, paper_dir):
    source_file = Path(source_file)
    safe_extensions = {".tex", ".bib", ".bbl", "sty", ".cls", ".bst"}

    if tarfile.is_tarfile(source_file):
        with tarfile.open(source_file) as tar:
            safe_members = [
                member for member in tar.getmembers()
                if member.isfile()
                and Path(member.name).suffix in safe_extensions
            ]
            tar.extractall(path=paper_dir, members=safe_members)
        source_file.unlink()

    elif is_gzip(source_file):
        try:
            with gzip.open(source_file, "rb") as gz:
                (paper_dir / "main.tex").write_bytes(content)
                source_file.unlink()
        except Exception:
            source_file.rename(paper_dir / "main.tex")
    
    else:
        source_file.rename(paper_dir / "main.tex")

    tex_files = list(paper_dir.glob("*.tex"))
    return len(tex_files) > 0

def download_paper(result, paper_dir):
    paper_dir.mkdir(parents=True, exist_ok=True)

    try:
        source_path = result.download_source(dirpath=str(paper_dir), filename="source")
    except Exception as error:
        if paper_dir.exists() and not any(paper_dir.iterdir()):
            paper_dir.rmdir()
        raise error
    
    has_tex = extract_source(source_path, paper_dir)

    if not has_tex:
        shutil.rmtree(paper_dir)
        return False
    
    return True


def build_metadata(result, arxiv_id, paper_dir):
    return {
        "arxiv_id": arxiv_id,
        "title": result.title,
        "authors": [author.name for author in result.authors],
        "categories": result.categories,
        "abstract": result.summary,
        "published": result.published.isoformat(),
        "updated": result.updated.isoformat() if result.updated else None,
        "pdf_url": result.pdf_url,
        "source_dir": str(paper_dir),
    }


def fetch_papers(config, max_override=None, dry_run=False):
    arxiv_config = config["arxiv"]
    paths = config["paths"]

    raw_dir = Path(paths["raw_sources"])
    metadata_dir = Path(paths["metadata"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = metadata_dir / "manifest.json"
    all_metadata, seen_ids = load_manifest(manifest_path)

    max_per_query = max_override or arxiv_config["max_results_per_query"]

    client = arxiv.Client(page_size=50, delay_seconds=arxiv_config["delay_seconds"], num_retries=3)

    stats = {"fetched": 0, "skipped": 0, "failed": 0, "no_tex": 0}

    for query in arxiv_config["queries"]:
        print(f"\n --- {query} ---")
        
        search = arxiv.Search(
        query=query,
        max_results=max_per_query,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    for result in client.results(search):
        arxiv_id = result.entry_id.split("/abs/")[-1]

        if arxiv_id in seen_ids:
            stats["skipped"] += 1
            continue
        seen_ids.add(arxiv_id)

        title_short = result.title[:70].replace("\n", " ")
        print(f" {arxiv_id}: {title_short}")

        if dry_run:
            stats["fetched"] += 1
            continue

        paper_dir = raw_dir / arxiv_id.replace("/", "_")

        try:
            success = download_paper(result, paper_dir)
        except Exception as error:
            print(f"[ERROR]  {error}.")
            stats["failed"] += 1
            continue

        if not success:
            print(f"[WARN] no .tex files found.")
            stats["no_tex"] += 1
            continue

        metadata = build_metadata(result, arxiv_id, paper_dir)

        with open(paper_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        all_metadata.append(metadata)
        save_manifest(manifest_path, all_metadata)
        stats["fetched"] +=1

    print(f"\n('=' * 50)")
    print(f"Done.")
    print(f"Fetched: {stats['fetched']}")
    print(f"Duplicates: {stats['skipped']}")
    print(f"No .tex: {stats['no_tex']}")
    print(f"Failed: {stats['failed']}")
    print(f"Total in manifest: {len(all_metadata)}")

    return all_metadata

def main():
    parser = argparse.ArgumentParser(description="Fetch integrable systems papers from arXiv.")
    parser.add_argument("--max", type=int, default=None, help="Override results per query.")
    parser.add_argument("--dry_run", action="store_true", help="Search and list papers without downloading.")
    args = parser.parse_args()

    config = load_config()
    fetch_papers(config, max_override=args.max, dry_run=args.dry_run)

if __name__ == "__main__":
    main()