"""Offline scoring parity, source scoping, persistence, migration and pipeline checks."""
import copy
import itertools
import pickle
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import yaml
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from inverted_bm25 import ARTIFACT_NAME, InvertedBM25, file_sha256
from main import RAGPipeline
from rebuild_bm25 import rebuild


ROOT = Path(__file__).resolve().parents[1]


def make_index(corpus, sources, **settings):
    chunks = [Document(page_content=" ".join(tokens), metadata={"source": source, "chunk_id": str(i)})
              for i, (tokens, source) in enumerate(zip(corpus, sources))]
    legacy = BM25Okapi(corpus, **settings)
    return chunks, legacy, InvertedBM25.from_legacy(chunks, legacy)


class ScoringTests(unittest.TestCase):
    def test_scores_and_top_k_match_scoped_legacy_including_edge_cases(self):
        rng = random.Random(207)
        corpus = [[rng.choice(["common", "common", "rare", "matrix", "vote", "graph", "table"])
                   for _ in range(rng.randint(1, 32))] for _ in range(61)]
        corpus[0] = []
        sources = ["abc"[i % 3] for i in range(len(corpus))]
        for k1, b, epsilon in ((1.5, .75, .25), (.8, 0, 0), (2, .9, .6)):
            chunks, _, index = make_index(corpus, sources, k1=k1, b=b, epsilon=epsilon)
            for size in (1, 2, 3):
                for scope in itertools.combinations("abc", size):
                    selected = [i for source in scope for i, value in enumerate(sources) if source == value]
                    baseline = BM25Okapi([corpus[i] for i in selected], k1=k1, b=b, epsilon=epsilon)
                    for query in ([], ["unknown"], ["vote"], ["vote", "vote", "common"], ["graph", "matrix", "table"]):
                        expected = dict(zip(selected, baseline.get_scores(query)))
                        ids, scores = index.score_candidates(query, scope)
                        actual = dict(zip(ids, scores))
                        np.testing.assert_allclose([actual.get(i, 0) for i in selected],
                                                   [expected[i] for i in selected], rtol=1e-12, atol=1e-12)
                        for threshold in (-1, 0, .5):
                            for top_k in (0, 3, 100):
                                wanted = sorted(((i, float(score)) for i, score in expected.items() if score > threshold),
                                                key=lambda item: (-item[1], item[0]))[:top_k]
                                got = index.search(query, scope, top_k, threshold)
                                # Numeric ties may differ by roundoff when IDF sums have a different order.
                                self.assertEqual(len(got), len(wanted))
                                np.testing.assert_allclose([v for _, v in got], [v for _, v in wanted], atol=1e-12)
                                self.assertTrue(all(sources[i] in scope for i, _ in got))

    def test_zero_and_negative_idf_thresholds(self):
        _, legacy, index = make_index([["same"], ["same", "same"], ["same"]], ["a"] * 3)
        self.assertLess(legacy.average_idf, 0)
        self.assertEqual(index.search(["same"], ["a"], 5), [])
        self.assertEqual(index.search(["unknown"], ["a"], 5, -.1), [(0, 0), (1, 0), (2, 0)])
        ids, scores = index.score_candidates(["same"], ["a"])
        np.testing.assert_allclose(scores, legacy.get_scores(["same"]))
        self.assertEqual(list(ids), [0, 1, 2])
        _, _, zero = make_index([["one"], ["two"]], ["a"] * 2)
        self.assertEqual(zero.search(["one"], ["a"], 5), [])

    def test_zero_nonmatches_outrank_negative_matches(self):
        _, legacy, index = make_index([["common", "same"], ["common", "same"], ["common", "same"], ["other", "same"]], ["a"] * 4)
        self.assertLess(legacy.get_scores(["common"])[0], 0)
        self.assertEqual(index.search(["common"], ["a"], 1, -1), [(3, 0)])

    def test_scope_cache_uses_saved_statistics_and_filters_before_top_k(self):
        _, _, index = make_index([["one", "rare"], ["one"], ["two", "rare"], ["two"]], ["a", "a", "b", "b"])
        first = index.scope(["b", "a"])
        self.assertIs(first, index.scope(["a", "b", "a"]))
        self.assertEqual([i for i, _ in index.search(["one"], ["b"], 5, -1)], [2, 3])
        with self.assertRaises(ValueError):
            index.search(["one"], ["missing"], 1)
        with self.assertRaises(ValueError):
            index.scope([])


class PersistenceTests(unittest.TestCase):
    def fixture(self, directory):
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.config = yaml.safe_load((ROOT / "config.yml").read_text())
        pipeline.persist_directory = Path(directory)
        pipeline.config["indexing"].update(mode="load", persist_directory=directory)
        pipeline.config["ablation"]["use_dense_retrieval"] = False
        pipeline.config["ablation"]["use_query_expansion"] = False
        pipeline.available_sources = ["a.pdf", "b.pdf"]
        pipeline.source_directory_names = {source: str(i) for i, source in enumerate(pipeline.available_sources)}
        pipeline.documents = [Document(page_content=text, metadata={"source": source, "page": page})
                              for page, (source, text) in enumerate((("a.pdf", "ﬁltering and neigh-\nboring pixels"),
                                                   ("a.pdf", "definitions of probability"),
                                                   ("a.pdf", "geometry and lines"),
                                                   ("b.pdf", "voting lines geometry")), start=1)]
        pipeline.chunks = pipeline.chunk_documents(pipeline.documents)
        pipeline.page_texts = {(doc.metadata["source"], doc.metadata["page"]): doc.page_content for doc in pipeline.documents}
        pipeline.structured_pages = {}
        pipeline.source_chunks = pipeline.group_chunks_by_source()
        pipeline.global_bm25 = pipeline.build_bm25(pipeline.chunks)
        pipeline.subset_bm25_cache = {(source,): (chunks, pipeline.build_bm25(chunks))
                                      for source, chunks in pipeline.source_chunks.items()}
        for kind in ("flat", "hnsw"):
            for source in pipeline.available_sources:
                path = pipeline.dense_index_path(kind, source)
                path.mkdir(parents=True)
                (path / "index.faiss").write_bytes(b"unchanged dense vectors")
                (path / "index.pkl").write_bytes(b"unchanged dense metadata")
        pipeline.save_index_data()
        return pipeline

    def test_persistence_rejects_stale_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.fixture(directory)
            loaded = InvertedBM25.load(directory, pipeline.chunks, pipeline.sparse_index_settings())
            self.assertEqual(loaded.chunk_ids, pipeline.inverted_bm25.chunk_ids)
            self.assertEqual(loaded._scopes, {})
            changed = copy.deepcopy(pipeline.chunks)
            changed[0].metadata["chunk_id"] = "different"
            with self.assertRaisesRegex(ValueError, "mapping"):
                InvertedBM25.load(directory, changed, pipeline.sparse_index_settings())
            with self.assertRaisesRegex(ValueError, "settings"):
                InvertedBM25.load(directory, pipeline.chunks, {})
            corpus_path = Path(directory) / "corpus.pkl"
            corpus_path.write_bytes(corpus_path.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "different persisted corpus"):
                InvertedBM25.load(directory, pipeline.chunks, pipeline.sparse_index_settings())

    def test_sparse_only_migration_preserves_corpus_and_dense_files(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.fixture(directory)
            artifact = Path(directory) / ARTIFACT_NAME
            artifact.unlink()
            hashes = {p: file_sha256(p) for p in Path(directory).rglob("*") if p.is_file()}
            with patch.object(RAGPipeline, "load_documents", side_effect=AssertionError("PDF read")), \
                 patch.object(RAGPipeline, "create_embedding_model", side_effect=AssertionError("embedding")), \
                 patch.object(RAGPipeline, "load_llm", side_effect=AssertionError("paid call")):
                rebuild(pipeline.config)
            self.assertTrue(artifact.is_file())
            self.assertEqual({p: file_sha256(p) for p in hashes}, hashes)

    def test_bm25_setting_migration_and_core_setting_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.fixture(directory)
            dense = {p: file_sha256(p) for p in Path(directory).rglob("index.*")}
            pipeline.config["retrieval"]["bm25_k1"] = 2.0
            pipeline.config["retrieval"]["bm25_token_pattern"] = "[a-z]+"
            rebuild(pipeline.config)
            loaded = InvertedBM25.load(directory, pipeline.chunks, pipeline.sparse_index_settings())
            self.assertEqual(loaded.k1, 2)
            self.assertEqual({p: file_sha256(p) for p in dense}, dense)
            with (Path(directory) / "corpus.pkl").open("rb") as stream:
                self.assertEqual(pickle.load(stream)["global_bm25"].k1, 2)
            pipeline.config["chunking"]["chunk_size"] += 1
            with self.assertRaisesRegex(ValueError, "rebuild"):
                rebuild(pipeline.config)

    def test_backends_toggles_and_exact_source_restrictions(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(directory)
            for backend in ("inverted", "rank_bm25"):
                config = copy.deepcopy(fixture.config)
                config["retrieval"]["bm25_backend"] = backend
                with patch.object(RAGPipeline, "load_llm", return_value=None), \
                     patch.object(RAGPipeline, "create_embedding_model", side_effect=AssertionError("dense disabled")):
                    pipeline = RAGPipeline(config, [])
                result = pipeline.retrieve_candidates('According to "a.pdf", filtering?', "filtering neighboring")
                self.assertTrue(result["bm25_results_with_scores"])
                self.assertTrue(all(doc.metadata["source"] == "a.pdf" for doc, _ in result["bm25_results_with_scores"]))
                self.assertEqual(result["dense_results_with_scores"], [])
                self.assertTrue(all(methods == ["BM25"] for methods in result["candidate_methods"].values()))
            (Path(directory) / ARTIFACT_NAME).unlink()
            config["retrieval"]["bm25_backend"] = "inverted"
            with patch.object(RAGPipeline, "load_llm", return_value=None), self.assertRaisesRegex(FileNotFoundError, "rebuild_bm25"):
                RAGPipeline(config, [])
            config["ablation"].update(use_dense_retrieval=True, use_bm25_retrieval=False)
            with patch.object(RAGPipeline, "load_llm", return_value=None), \
                 patch.object(RAGPipeline, "create_embedding_model", return_value=None), \
                 patch.object(RAGPipeline, "load_dense_indexes", return_value={}):
                pipeline = RAGPipeline(config, [])
            config["ablation"].update(use_dense_retrieval=False)
            with self.assertRaisesRegex(ValueError, "At least one"):
                RAGPipeline(config, [])

    def test_flat_and_hnsw_merge_bm25_with_dense_and_deduplicate(self):
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.fixture(directory)
            pipeline.use_bm25_retrieval = pipeline.use_dense_retrieval = True
            pipeline.embedding_model = Mock()
            for dense_type in ("flat", "hnsw"):
                for backend in ("inverted", "rank_bm25"):
                    pipeline.config["retrieval"].update(dense_index_type=dense_type, bm25_backend=backend)
                    store = Mock()
                    store.similarity_search_with_score_by_vector.return_value = [(pipeline.chunks[0], .1)]
                    pipeline.source_vector_stores = {"a.pdf": store}
                    result = pipeline.retrieve_candidates('"a.pdf" filtering', "filtering")
                    self.assertEqual(result["candidate_methods"][pipeline.chunks[0].metadata["chunk_id"]], ["dense", "BM25"])
                    self.assertEqual(len(result["candidate_docs"]), 1)

    def test_incompatible_backend_is_rejected_before_loading_models(self):
        config = yaml.safe_load((ROOT / "config.yml").read_text())
        config["retrieval"]["bm25_backend"] = "unknown"
        with patch.object(RAGPipeline, "load_llm", side_effect=AssertionError("model load")), \
             self.assertRaisesRegex(ValueError, "bm25_backend"):
            RAGPipeline(config, [])

    def test_build_saves_both_backends_even_with_bm25_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(directory)
            config = copy.deepcopy(fixture.config)
            config["indexing"]["mode"] = "build"
            config["ablation"].update(use_dense_retrieval=True, use_bm25_retrieval=False)
            with patch.object(RAGPipeline, "load_documents", return_value=fixture.documents), \
                 patch.object(RAGPipeline, "build_dense_indexes", return_value={}), \
                 patch.object(RAGPipeline, "create_embedding_model", return_value=None), \
                 patch.object(RAGPipeline, "load_llm", return_value=None):
                pipeline = RAGPipeline(config, [Path(source) for source in fixture.available_sources])
            self.assertTrue((Path(directory) / ARTIFACT_NAME).is_file())
            with (Path(directory) / "corpus.pkl").open("rb") as stream:
                self.assertIsInstance(pickle.load(stream)["global_bm25"], BM25Okapi)
            self.assertEqual(len(pipeline.inverted_bm25.chunk_ids), len(fixture.chunks))


if __name__ == "__main__":
    unittest.main()
