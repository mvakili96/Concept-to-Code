"""Postings-based BM25 with rank_bm25.BM25Okapi's scoring formula.

Each token points to the chunks containing it and their term frequencies. Source
scopes use their own document frequencies, lengths and epsilon IDF floor, just as
building BM25Okapi over those chunks would. No PDF parsing or models are used here.
"""
import hashlib
import heapq
import math
import os
import pickle
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np


FORMAT_VERSION = 1
ARTIFACT_NAME = "bm25-inverted.pkl"


def file_sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def atomic_pickle(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class InvertedBM25:
    def __init__(self, chunk_ids, sources, term_frequencies, lengths, k1, b, epsilon):
        self.chunk_ids = tuple(chunk_ids)
        self.sources = tuple(sources)
        if len(set(self.chunk_ids)) != len(self.chunk_ids):
            raise ValueError("BM25 chunk IDs must be unique.")
        if not self.chunk_ids or not (len(self.chunk_ids) == len(self.sources) == len(term_frequencies) == len(lengths)):
            raise ValueError("BM25 requires a nonempty, aligned chunk corpus.")
        self.k1, self.b, self.epsilon = k1, b, epsilon
        self.doc_lengths = np.asarray(lengths, dtype=np.float64)
        self.source_names = tuple(dict.fromkeys(self.sources))
        codes = {source: index for index, source in enumerate(self.source_names)}
        self.source_codes = np.asarray([codes[source] for source in self.sources], dtype=np.int32)
        self.source_stats = {source: {"count": 0, "length": 0, "df": Counter()} for source in codes}
        postings = {}
        for index, (source, frequencies) in enumerate(zip(self.sources, term_frequencies)):
            stats = self.source_stats[source]
            stats["count"] += 1
            stats["length"] += int(self.doc_lengths[index])
            stats["df"].update(frequencies.keys())
            for token, frequency in frequencies.items():
                ids, counts = postings.setdefault(token, ([], []))
                ids.append(index)
                counts.append(frequency)
        self.postings = {token: (np.asarray(ids, dtype=np.int32), np.asarray(counts, dtype=np.float64))
                         for token, (ids, counts) in postings.items()}
        # Query-time scope caches are derived from saved aggregates, never retokenized text.
        self._scopes = {}

    @classmethod
    def from_legacy(cls, chunks, index):
        return cls([chunk.metadata["chunk_id"] for chunk in chunks],
                   [chunk.metadata["source"] for chunk in chunks], index.doc_freqs,
                   index.doc_len, index.k1, index.b, index.epsilon)

    def scope(self, sources):
        key = tuple(sorted(set(sources)))
        if not key or set(key) - set(self.source_names):
            raise ValueError("BM25 requires known, nonempty source restrictions.")
        if key not in self._scopes:
            df = Counter()
            count = total_length = 0
            for source in key:
                stats = self.source_stats[source]
                count += stats["count"]
                total_length += stats["length"]
                df.update(stats["df"])
            idf = {token: math.log(count - frequency + .5) - math.log(frequency + .5)
                   for token, frequency in df.items()}
            # BM25Okapi floors negative IDF using the average over ALL scope terms.
            floor = self.epsilon * sum(idf.values()) / len(idf) if idf else 0.0
            idf = {token: floor if value < 0 else value for token, value in idf.items()}
            codes = np.asarray([self.source_names.index(source) for source in key])
            self._scopes[key] = (count, total_length / count, idf, codes)
        return self._scopes[key]

    def score_candidates(self, tokens, sources):
        """Return global chunk positions and scores only for nonzero-IDF matches.

        Repeated tokens contribute repeatedly, as in BM25Okapi. The production
        caller still deduplicates query tokens before either backend is called.
        """
        count, avgdl, idf, codes = self.scope(sources)
        ids_parts, score_parts = [], []
        if avgdl == 0:
            return np.array([], dtype=np.int32), np.array([], dtype=np.float64)
        for token in tokens:
            weight = idf.get(token, 0)
            if not weight or token not in self.postings:
                continue
            ids, frequencies = self.postings[token]
            if count != len(self.chunk_ids):
                eligible = np.isin(self.source_codes[ids], codes)
                ids, frequencies = ids[eligible], frequencies[eligible]
            if len(ids):
                scores = weight * (frequencies * (self.k1 + 1) / (
                    frequencies + self.k1 * (1 - self.b + self.b * self.doc_lengths[ids] / avgdl)))
                ids_parts.append(ids)
                score_parts.append(scores)
        if not ids_parts:
            return np.array([], dtype=np.int32), np.array([], dtype=np.float64)
        ids, inverse = np.unique(np.concatenate(ids_parts), return_inverse=True)
        return ids, np.bincount(inverse, weights=np.concatenate(score_parts), minlength=len(ids))

    def search(self, tokens, sources, top_k, min_score=0.0):
        ids, scores = self.score_candidates(tokens, sources)
        if min_score < 0:
            # Zero-score nonmatches can beat negative matches. Preserve this unusual
            # legacy setting, even though it requires considering all eligible chunks.
            codes = self.scope(sources)[3]
            eligible = np.flatnonzero(np.isin(self.source_codes, codes))
            all_scores = np.zeros(len(eligible))
            all_scores[np.searchsorted(eligible, ids)] = scores
            ids, scores = eligible, all_scores
        candidates = ((int(index), float(score)) for index, score in zip(ids, scores) if score > min_score)
        # Deterministic ties prefer the earlier corpus position. Legacy argsort ties
        # were unspecified. Avoid sorting the whole score vector to select a small k.
        return heapq.nlargest(top_k, candidates, key=lambda item: (item[1], -item[0]))

    def save(self, directory, settings):
        directory = Path(directory)
        cache = self._scopes
        self._scopes = {}
        try:
            atomic_pickle(directory / ARTIFACT_NAME, dict(
                format_version=FORMAT_VERSION, settings=settings,
                corpus_sha256=file_sha256(directory / "corpus.pkl"), index=self))
        finally:
            self._scopes = cache

    @classmethod
    def load(cls, directory, chunks, settings):
        directory = Path(directory)
        path = directory / ARTIFACT_NAME
        rebuild = "Run python rebuild_bm25.py to rebuild only sparse indexes from persisted chunks."
        if not path.is_file():
            raise FileNotFoundError(f"Missing inverted BM25 index. {rebuild}")
        # Like corpus.pkl and FAISS metadata, only load locally generated trusted pickle files.
        with path.open("rb") as stream:
            data = pickle.load(stream)
        if data.get("format_version") != FORMAT_VERSION or data.get("settings") != settings:
            raise ValueError(f"Incompatible inverted BM25 format or settings. {rebuild}")
        if data.get("corpus_sha256") != file_sha256(directory / "corpus.pkl"):
            raise ValueError(f"Inverted BM25 belongs to a different persisted corpus. {rebuild}")
        index = data["index"]
        if (not isinstance(index, cls) or index.chunk_ids != tuple(c.metadata["chunk_id"] for c in chunks)
                or index.sources != tuple(c.metadata["source"] for c in chunks)):
            raise ValueError(f"Inverted BM25 chunk mapping changed. {rebuild}")
        return index
