"""
Production script to embed municipal ordinances using ADVANCED semantic chunking

Usage:
    python scripts/embed_ordinances.py --city "Gainesville"
"""

import argparse
import json
import hashlib
from pathlib import Path
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import time
from tqdm import tqdm
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.services.advanced_chunking_service import create_advanced_chunker


def chunk_ordinance_by_sections(ordinance_text: str, max_chunk_size: int = 1000) -> List[Dict]:
    """Chunk ordinance using ADVANCED semantic chunking"""
    print(f"\n[CHUNKING] Using ADVANCED semantic chunker...")

    chunker = create_advanced_chunker(
        target_words=400,
        max_words=500,
        overlap_sentences=2,
        use_semantic_boundaries=True,
        embedding_model_name="BAAI/bge-small-en-v1.5"
    )

    chunks = chunker.chunk_ordinance(ordinance_text)

    print(f"[CHUNKING] Created {len(chunks)} semantic chunks")
    print(f"[CHUNKING] Avg: {sum(c.word_count for c in chunks) / len(chunks):.0f} words/chunk")

    return [chunk.to_dict() for chunk in chunks]


def embed_ordinances(
    ordinance_dir: str,
    model_name: str = "BAAI/bge-large-en-v1.5",
    output_dir: str = "data/embeddings/",
    device: str = "cpu"
):
    """Main embedding function"""
    print("=" * 70)
    print("DOMINION ORDINANCE EMBEDDING PIPELINE")
    print("=" * 70)

    print(f"\n1. Loading model: {model_name}...")
    start = time.time()
    model = SentenceTransformer(model_name, device=device)
    load_time = time.time() - start
    print(f"   Model loaded in {load_time:.2f}s")
    print(f"   Dimensions: {model.get_sentence_embedding_dimension()}")

    print(f"\n2. Scanning for ordinances in {ordinance_dir}...")
    ordinance_path = Path(ordinance_dir)
    ordinance_files = list(ordinance_path.glob("**/*.json"))
    print(f"   Found {len(ordinance_files)} ordinance files")

    if len(ordinance_files) == 0:
        print("   [!] No ordinance files found. Run scrapers first!")
        return

    total_chunks = 0
    total_ordinances = 0
    all_embeddings = []

    print(f"\n3. Processing ordinances...")

    for ord_file in tqdm(ordinance_files, desc="Ordinances"):
        try:
            with open(ord_file, 'r', encoding='utf-8') as f:
                ordinance = json.load(f)

            full_text = ordinance.get('content', '')
            if not full_text:
                continue

            chunks = chunk_ordinance_by_sections(full_text)
            chunk_texts = [chunk['text'] for chunk in chunks]

            embeddings = model.encode(
                chunk_texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                all_embeddings.append({
                    "ordinance_file": str(ord_file.name),
                    "city": ordinance.get('city', 'unknown'),
                    "state": ordinance.get('state', 'FL'),
                    "chunk_number": chunk['chunk_number'],
                    "chunk_text": chunk['text'],
                    "chunk_chars": chunk['char_count'],
                    "embedding": embedding.tolist(),
                    "content_hash": hashlib.sha256(chunk['text'].encode()).hexdigest()
                })

            total_chunks += len(chunks)
            total_ordinances += 1

        except Exception as e:
            print(f"   [!] Error processing {ord_file.name}: {e}")
            continue

    print(f"\n4. Saving embeddings...")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = output_path / f"ordinance_embeddings_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "model": model_name,
                "dimensions": model.get_sentence_embedding_dimension(),
                "total_ordinances": total_ordinances,
                "total_chunks": total_chunks,
                "created_at": timestamp,
                "device": device
            },
            "embeddings": all_embeddings
        }, f, indent=2)

    print(f"   Saved to: {output_file}")
    print(f"   Size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("=" * 70)
    print(f"Ordinances processed: {total_ordinances}")
    print(f"Total chunks: {total_chunks}")
    print(f"Average chunks per ordinance: {total_chunks / max(total_ordinances, 1):.1f}")
    print(f"Embeddings file: {output_file}")
    print("\nNext step: Load these embeddings into the database")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Embed municipal ordinances")
    parser.add_argument("--input-dir", type=str, default="data/ordinances")
    parser.add_argument("--output-dir", type=str, default="data/embeddings")
    parser.add_argument("--model", type=str, default="BAAI/bge-large-en-v1.5")
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--city", type=str, help="Filter by city")
    args = parser.parse_args()

    if args.city:
        print(f"Filtering for city: {args.city}")

    embed_ordinances(
        ordinance_dir=args.input_dir,
        model_name=args.model,
        output_dir=args.output_dir,
        device=args.device
    )


if __name__ == "__main__":
    main()
