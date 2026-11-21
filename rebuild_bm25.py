"""Rebuild sparse indexes from trusted persisted chunks, without PDFs or models."""
import argparse
import json
import os
import pickle
import tempfile
from pathlib import Path

import yaml

from inverted_bm25 import InvertedBM25, atomic_pickle


def rebuild(config):
    from main import RAGPipeline

    pipeline = RAGPipeline.__new__(RAGPipeline)
    pipeline.config = config
    pipeline.persist_directory = Path(config["indexing"]["persist_directory"])
    # Refuse changes that also invalidate chunks, embeddings, or the HNSW graph.
    # This path never creates an embedding model, reranker, PDF extractor, or LLM.
    pipeline.load_index_data(load_sparse=False, allow_bm25_rebuild=True)
    manifest_path = pipeline.persist_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    settings = pipeline.persisted_index_settings()
    changed = manifest["index_settings"]["bm25"] != settings["bm25"]
    if changed:
        pipeline.global_bm25 = pipeline.build_bm25(pipeline.chunks)
        pipeline.subset_bm25_cache = {
            (source,): (chunks, pipeline.build_bm25(chunks))
            for source, chunks in pipeline.source_chunks.items()
        }
        corpus_path = pipeline.persist_directory / "corpus.pkl"
        with corpus_path.open("rb") as stream:
            corpus = pickle.load(stream)
        corpus.update(global_bm25=pipeline.global_bm25, subset_bm25_cache=pipeline.subset_bm25_cache)
        atomic_pickle(corpus_path, corpus)
    index = InvertedBM25.from_legacy(pipeline.chunks, pipeline.global_bm25)
    index.save(pipeline.persist_directory, pipeline.sparse_index_settings())
    if changed:
        manifest["index_settings"]["bm25"] = settings["bm25"]
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=pipeline.persist_directory, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(manifest, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Saved inverted BM25 for {len(pipeline.chunks)} chunks to {pipeline.persist_directory}.")
    print("Legacy BM25 is also available. PDF text, chunk IDs, and FAISS files are unchanged.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yml", help="Configuration file (default: config.yml).")
    args = parser.parse_args(argv)
    with Path(args.config).open(encoding="utf-8") as stream:
        rebuild(yaml.safe_load(stream))


if __name__ == "__main__":
    main()
