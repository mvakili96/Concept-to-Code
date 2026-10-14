#########################################################################################################################################
# 1- Load the document
#########################################################################################################################################
import json
import pickle
import re
import unicodedata
from pathlib import Path

import faiss
import pypdf
import yaml
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi
from transformers import GenerationConfig


def find_explicit_sources(question, available_sources):
    # Example: according to "Probabilistic Machine Learning.pdf", what is ...?
    mentioned_names = re.findall(
        r"\baccording to\s+(?:the\s+(?:file|document)\s+)?[\"\u201c']([^\"\u201d']+)[\"\u201d']",
        question,
        flags=re.IGNORECASE
    )

    matched_sources = []

    for mentioned_name in mentioned_names:
        for source in available_sources:
            if mentioned_name == source:
                if source not in matched_sources:
                    matched_sources.append(source)

    return matched_sources


class ConversationSession:
    def __init__(self):
        # Both roles are kept because a follow-up such as "explain the second one"
        # may refer to content that appeared in the previous answer.
        self.messages = []
        self.active_sources = []


class RAGPipeline:
    PERSISTENCE_FORMAT_VERSION = 1

    def __init__(self, config, pdf_paths):
        self.config = config
        self.pdf_paths = pdf_paths
        self.indexing_mode = self.config["indexing"]["mode"]
        self.persist_directory = Path(
            self.config["indexing"]["persist_directory"]
        )
        self.use_dense_retrieval = self.config["ablation"]["use_dense_retrieval"]
        self.use_bm25_retrieval = self.config["ablation"]["use_bm25_retrieval"]
        self.use_query_expansion = self.config["ablation"]["use_query_expansion"]

        if self.indexing_mode not in ("build", "load"):
            raise ValueError('indexing.mode must be either "build" or "load".')
        if not self.use_dense_retrieval and not self.use_bm25_retrieval:
            raise ValueError(
                "At least one of ablation.use_dense_retrieval or "
                "ablation.use_bm25_retrieval must be enabled."
            )
        if self.config["conversation"]["max_history_turns"] < 1:
            raise ValueError("conversation.max_history_turns must be at least 1.")

        self.page_texts = {}

        if self.indexing_mode == "build":
            self.available_sources = [pdf_path.name for pdf_path in pdf_paths]
            self.documents = self.load_documents()
            self.chunks = self.chunk_documents(self.documents)
            self.source_chunks = self.group_chunks_by_source()
            self.source_directory_names = {
                source: f"source_{index:03d}"
                for index, source in enumerate(self.available_sources)
            }
            self.embedding_model = self.create_embedding_model()
            self.source_vector_stores = self.build_dense_indexes()
            self.global_bm25 = self.build_bm25(self.chunks)
            self.subset_bm25_cache = {
                (source,): (chunks, self.build_bm25(chunks))
                for source, chunks in self.source_chunks.items()
            }
            self.save_index_data()
        else:
            self.load_index_data()
            self.embedding_model = (
                self.create_embedding_model() if self.use_dense_retrieval else None
            )
            self.source_vector_stores = (
                self.load_dense_indexes() if self.use_dense_retrieval else {}
            )

        self.llm = self.load_llm()
        self.reranker = None

    def group_chunks_by_source(self):
        return {
            source: [
                chunk
                for chunk in self.chunks
                if chunk.metadata["source"] == source
            ]
            for source in self.available_sources
        }

    def persisted_index_settings(self):
        # These settings affect the saved chunks, embeddings, BM25 index, or HNSW graph.
        # Query-time settings such as top-k and hnsw_ef_search may change without rebuilding.
        return {
            "chunking": self.config["chunking"],
            "embedding": self.config["embedding"],
            "bm25": {
                key: self.config["retrieval"][key]
                for key in (
                    "bm25_k1",
                    "bm25_b",
                    "bm25_epsilon",
                    "bm25_token_pattern",
                )
            },
            "hnsw_construction": {
                "hnsw_m": self.config["retrieval"]["hnsw_m"],
                "hnsw_ef_construction": self.config["retrieval"]["hnsw_ef_construction"],
            },
        }

    def dense_index_path(self, dense_index_type, source):
        return (
            self.persist_directory
            / "faiss"
            / dense_index_type
            / self.source_directory_names[source]
        )

    def save_index_data(self):
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # BM25 and LangChain Documents are Python objects, so this local artifact is
        # intended to be loaded only from a trusted index directory created here.
        persisted_data = {
            "documents": self.documents,
            "chunks": self.chunks,
            "page_texts": self.page_texts,
            "global_bm25": self.global_bm25,
            "subset_bm25_cache": self.subset_bm25_cache,
        }
        with (self.persist_directory / "corpus.pkl").open("wb") as file:
            pickle.dump(persisted_data, file)

        manifest = {
            "format_version": self.PERSISTENCE_FORMAT_VERSION,
            "available_sources": self.available_sources,
            "source_directory_names": self.source_directory_names,
            "index_settings": self.persisted_index_settings(),
            "dense_indexes": ["flat", "hnsw"],
        }
        (self.persist_directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("Saved persisted corpus and indexes to:", self.persist_directory)

    def load_index_data(self):
        manifest_path = self.persist_directory / "manifest.json"
        corpus_path = self.persist_directory / "corpus.pkl"

        if not manifest_path.is_file() or not corpus_path.is_file():
            raise FileNotFoundError(
                f"No complete persisted index was found in {self.persist_directory}. "
                'Set indexing.mode to "build" and run the pipeline first.'
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format_version") != self.PERSISTENCE_FORMAT_VERSION:
            raise ValueError(
                "The persisted index format is incompatible with this code. "
                'Set indexing.mode to "build" to rebuild it.'
            )

        if manifest.get("index_settings") != self.persisted_index_settings():
            raise ValueError(
                "Chunking, embedding, BM25, or HNSW construction settings changed "
                "after the indexes were built. Set indexing.mode to \"build\" to rebuild them."
            )

        if set(manifest.get("dense_indexes", [])) != {"flat", "hnsw"}:
            raise ValueError(
                "The persisted data does not contain both Flat and HNSW indexes. "
                'Set indexing.mode to "build" to rebuild it.'
            )

        self.available_sources = manifest["available_sources"]
        self.source_directory_names = manifest["source_directory_names"]

        try:
            # Pickle must only be loaded from this locally generated, trusted directory.
            with corpus_path.open("rb") as file:
                persisted_data = pickle.load(file)
        except Exception as error:
            raise RuntimeError(
                "The persisted corpus data could not be loaded. "
                'Set indexing.mode to "build" to rebuild it.'
            ) from error

        self.documents = persisted_data["documents"]
        self.chunks = persisted_data["chunks"]
        self.page_texts = persisted_data["page_texts"]
        self.global_bm25 = persisted_data["global_bm25"]
        self.subset_bm25_cache = persisted_data["subset_bm25_cache"]
        self.source_chunks = self.group_chunks_by_source()

        for dense_index_type in ("flat", "hnsw"):
            for source in self.available_sources:
                index_path = self.dense_index_path(dense_index_type, source)
                if not (index_path / "index.faiss").is_file() or not (
                    index_path / "index.pkl"
                ).is_file():
                    raise FileNotFoundError(
                        f"The persisted {dense_index_type} index for {source} is missing. "
                        'Set indexing.mode to "build" to rebuild all indexes.'
                    )

        print("Loaded persisted corpus data from:", self.persist_directory)

    def load_documents(self):
        documents = []

        for pdf_path in self.pdf_paths:
            reader = pypdf.PdfReader(pdf_path)

            for page_number, page in enumerate(reader.pages):

                # the following text totally ignores figures. Object type is a string.
                text = page.extract_text() or ""
                self.page_texts[(pdf_path.name, page_number + 1)] = text

                doc = Document(
                    page_content=text,
                    metadata={
                        "source": pdf_path.name,
                        "page": page_number + 1
                    }
                )

                documents.append(doc)

        print(200*"#")
        print("DONE with parsing the reference files!")
        print(200*"#")
        return documents

    #########################################################################################################################################
    # 2- Chunk the document
    #########################################################################################################################################
    def chunk_documents(self, documents):
        # LangChain's recursive splitter tries paragraph boundaries first, then progressively smaller separators instead of blindly cutting every N characters.
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config["chunking"]["chunk_size"],
            chunk_overlap=self.config["chunking"]["chunk_overlap"],
            add_start_index=self.config["chunking"]["add_start_index"]
        )

        # chunks is a list of chunks. Each chunk has metadata such as page_content, source, page, start_index, and so on.
        # Here, start_index means the index of the first character of this chunk corresponds to character start_index of the original pagetext.
        chunks = splitter.split_documents(documents)

        # This ID is stored in both retrieval systems so the same chunk can be
        # recognized and deduplicated after dense and sparse retrieval.
        for chunk in chunks:
            chunk.metadata["chunk_id"] = (
                f"{chunk.metadata['source']}::"
                f"page={chunk.metadata['page']}::"
                f"start={chunk.metadata['start_index']}"
            )

        return chunks

    #########################################################################################################################################
    # 3- Turn chunks into embeddings
    #########################################################################################################################################
    def create_embedding_model(self):
        embedding_model = HuggingFaceEmbeddings(
            model_name=self.config["embedding"]["model_name"],
            encode_kwargs={
                "normalize_embeddings": self.config["embedding"]["normalize_embeddings"]
            }
        )

        return embedding_model

    """
    Analyze and diagnose embeddings:
    text = chunks[50].page_content
    vector = embedding_model.embed_query(text)

    print(type(vector))
    print("Embedding dimensions:", len(vector))
    print(vector[:10])
    """

    #########################################################################################################################################
    # 4- Build the dense and sparse retrieval indexes
    #########################################################################################################################################
    def tokenize_for_bm25(self, text):
        return re.findall(
            self.config["retrieval"]["bm25_token_pattern"],
            text.lower()
        )

    def build_faiss_vector_store(self, chunks, embeddings, dense_index_type):
        text_embeddings = list(
            zip(
                [chunk.page_content for chunk in chunks],
                embeddings,
            )
        )
        metadatas = [chunk.metadata for chunk in chunks]
        chunk_ids = [chunk.metadata["chunk_id"] for chunk in chunks]

        if dense_index_type == "flat":
            return FAISS.from_embeddings(
                text_embeddings=text_embeddings,
                embedding=self.embedding_model,
                metadatas=metadatas,
                ids=chunk_ids,
            )
        if dense_index_type == "hnsw":
            faiss_index = faiss.IndexHNSWFlat(
                len(embeddings[0]),
                self.config["retrieval"]["hnsw_m"]
            )
            faiss_index.hnsw.efConstruction = self.config["retrieval"]["hnsw_ef_construction"]
            faiss_index.hnsw.efSearch = self.config["retrieval"]["hnsw_ef_search"]
            vector_store = FAISS(
                embedding_function=self.embedding_model,
                index=faiss_index,
                docstore=InMemoryDocstore(),
                index_to_docstore_id={}
            )
            vector_store.add_embeddings(
                text_embeddings=text_embeddings,
                metadatas=metadatas,
                ids=chunk_ids,
            )
            return vector_store

        raise ValueError('retrieval.dense_index_type must be either "flat" or "hnsw".')

    def build_dense_indexes(self):
        # LangChain's vector-store abstraction exists to associate embeddings with their original documents and perform similarity search over them.
        # In the earlier single-query layout:
        # When a source was named, chunks contains only that source. Otherwise, it
        # contains all chunks from all sources in one global FAISS index.
        # Each source has its own FAISS index. Searching every source index and
        # merging the results lets the same pipeline restrict retrieval per query.
        # Each chunk is embedded once, and those same embeddings are used to build
        # both exact IndexFlatL2 and approximate IndexHNSWFlat indexes. The config
        # selects which persisted index is used for retrieval.
        dense_index_type = self.config["retrieval"]["dense_index_type"]
        if dense_index_type not in ("flat", "hnsw"):
            raise ValueError('retrieval.dense_index_type must be either "flat" or "hnsw".')

        source_vector_stores = {}
        for source, chunks in self.source_chunks.items():
            if not chunks:
                raise ValueError(f"No extractable text chunks were found for {source}.")

            embeddings = self.embedding_model.embed_documents(
                [chunk.page_content for chunk in chunks]
            )

            for index_type in ("flat", "hnsw"):
                vector_store = self.build_faiss_vector_store(
                    chunks,
                    embeddings,
                    index_type,
                )
                vector_store.save_local(
                    str(self.dense_index_path(index_type, source))
                )

                if index_type == dense_index_type:
                    source_vector_stores[source] = vector_store

        print("Built and persisted FAISS indexes: flat, hnsw")
        print("Dense FAISS index selected for retrieval:", dense_index_type)
        return source_vector_stores

    def load_dense_indexes(self):
        dense_index_type = self.config["retrieval"]["dense_index_type"]
        if dense_index_type not in ("flat", "hnsw"):
            raise ValueError('retrieval.dense_index_type must be either "flat" or "hnsw".')

        source_vector_stores = {}
        for source in self.available_sources:
            # FAISS stores the document metadata in a pickle beside the native index.
            # Loading is safe here only because these files were created locally by
            # this pipeline in the configured trusted directory.
            vector_store = FAISS.load_local(
                str(self.dense_index_path(dense_index_type, source)),
                self.embedding_model,
                allow_dangerous_deserialization=True,
            )

            if dense_index_type == "hnsw":
                vector_store.index.hnsw.efSearch = self.config["retrieval"][
                    "hnsw_ef_search"
                ]

            source_vector_stores[source] = vector_store

        print("Dense FAISS index loaded for retrieval:", dense_index_type)
        return source_vector_stores

    def build_bm25(self, chunks):
        # Unlike a vector store, BM25 indexes tokenized words(so here, by token, we mean a word) rather than embeddings.
        # It is built once during ingestion and reused for every query.
        # bm25_corpus is a list of all chunks, each chunk represented with a list of its words as strings
        bm25_corpus = [self.tokenize_for_bm25(chunk.page_content) for chunk in chunks]
        return BM25Okapi(
            bm25_corpus,
            k1=self.config["retrieval"]["bm25_k1"],
            b=self.config["retrieval"]["bm25_b"],
            epsilon=self.config["retrieval"]["bm25_epsilon"]
        )

    def bm25_for_sources(self, sources):
        source_key = tuple(sorted(sources))

        if len(source_key) == len(self.available_sources):
            return self.chunks, self.global_bm25

        if source_key not in self.subset_bm25_cache:
            chunks = [
                chunk
                for source in source_key
                for chunk in self.source_chunks[source]
            ]
            self.subset_bm25_cache[source_key] = (
                chunks,
                self.build_bm25(chunks)
            )

        return self.subset_bm25_cache[source_key]

    """
    For huge documents, the index can be saved with vector_store.save_local(...),
    then loaded on later runs so the chunks do not need to be embedded again.

    LangChain’s FAISS vector store is like this:
    FAISS Vector Store
    │
    ├── index
    │   ├── vector 0  → [0.12, -0.43, 0.08, ...]
    │   ├── vector 1  → [0.31,  0.17, -0.22, ...]
    │   └── vector 2  → [-0.14, 0.52, 0.09, ...]
    │
    ├── index_to_docstore_id
    │   ├── 0 → "abc123"
    │   ├── 1 → "def456"
    │   └── 2 → "ghi789"
    │
    └── docstore
        ├── "abc123"
        │    ├── page_content: "Machine learning is..."
        │    └── metadata: {page: 1, start_index: 0}
        │
        ├── "def456"
        │    ├── page_content: "Neural networks are..."
        │    └── metadata: {page: 1, start_index: 850}
        │
        └── "ghi789"
             ├── page_content: "Transformers use..."
             └── metadata: {page: 2, start_index: 0}


    To inspect vector store:

    vector = vector_store.index.reconstruct(0)
    print(vector)
    index_to_docstore_id = vector_store.index_to_docstore_id[0]
    print(index_to_docstore_id)
    doc = vector_store.docstore.search(index_to_docstore_id)
    print(doc)

    To inspect bm25_index:

    Following shows all available attributes/methods you can access with bm25_index.something.
    print(dir(bm25_index))

    Following shows a dict for each chunk, with key being the word inside the chunk and value being the frequency of the word inside the chunk
    for freq_dict in bm25_index.doc_freqs:
        print(freq_dict)

    bm25_index.idf["draft"] measures each token’s importance across all chunks.
    idf = Inverse Document Frequency. It measures how rare a word is across your chunks.
    In rank_bm25, roughly:
    IDF(t)= log[(N-df(t)+0.5)/(df(t)+0.5)]
    where:
    N = total number of chunks
    df(t) = number of chunks containing that word
    So:
    word appears in few chunks → high IDF → more informative
    word appears in many chunks → low IDF → less informative

    bm25_index.get_scores(query_tokens) → BM25 score for every chunk for a query.
    rank_bm25.get_scores() effectively scores every chunk in doc_freqs. So it is brute-force over the corpus rather than using an inverted index.
    For each query word and each chunk, BM25 combines:
    score = IDF(q) * TF(q,d)*(k_1+1) / (TF(q,d)+k_1(1-b+b*|d|/avgdl))
    where:
    IDF(q) = how rare the query word is across chunks
    TF(q,d) = how many times it occurs in that chunk
    |d| = chunk length
    avgdl = average chunk length
    Then it adds the scores for all query words. So for a query, it's key/important/rare words already contribute a lot
    to the aggregate score, whereas the common words add only a bit.
    Therefore, LLM for matching is mainly used for extracting synonyms, rather than localizing keywords
    One limitation of BM25 is its unawareness about a combo of keywords like "neural radiance field", even though it
    handles all its rare words.
    """

    #########################################################################################################################################
    # 5- Load a local LLM and expand the query for BM25
    #########################################################################################################################################
    def load_llm(self):
        generation_config = GenerationConfig.from_pretrained(
            self.config["llm"]["model_id"]
        )

        generation_config.max_new_tokens = self.config["llm"]["generation"]["max_new_tokens"]
        generation_config.do_sample = self.config["llm"]["generation"]["do_sample"]

        # These only matter when sampling is enabled
        generation_config.temperature = self.config["llm"]["generation"]["temperature"]
        generation_config.top_p = self.config["llm"]["generation"]["top_p"]
        generation_config.top_k = self.config["llm"]["generation"]["top_k"]

        return HuggingFacePipeline.from_model_id(
            model_id=self.config["llm"]["model_id"],
            task=self.config["llm"]["task"],

            pipeline_kwargs={
                "generation_config": generation_config,
                "return_full_text": self.config["llm"]["return_full_text"],
            },

            device_map=self.config["llm"]["device_map"],
        )

    def keep_conservative_terms(self, values, maximum):
        kept_terms = []
        seen_terms = set()

        if not isinstance(values, list):
            return kept_terms

        for value in values:
            if not isinstance(value, str):
                continue

            term = value.strip()
            normalized_term = term.lower()

            if (
                term
                and len(term) <= self.config["query_expansion"]["max_term_length"]
                and normalized_term not in seen_terms
            ):
                kept_terms.append(term)
                seen_terms.add(normalized_term)

        return kept_terms[:maximum]

    def expand_query(self, query):
        expansion_prompt = self.config["query_expansion"]["prompt"].format(
            query=query,
            max_key_terms=self.config["query_expansion"]["max_key_terms"],
            max_acronyms=self.config["query_expansion"]["max_acronyms"],
            min_variations=self.config["query_expansion"]["min_variations"],
            max_variations=self.config["query_expansion"]["max_variations"]
        )

        expansion_response = self.llm.invoke(
            expansion_prompt,
            pipeline_kwargs={
                "max_new_tokens": self.config["query_expansion"]["max_new_tokens"]
            }
        )
        json_start = expansion_response.find("{")

        try:
            # raw_decode reads the first complete JSON object and ignores any text the
            # LLM may have generated after it.
            parsed_expansion, _ = json.JSONDecoder().raw_decode(
                expansion_response[json_start:]
            ) if json_start != -1 else ({}, 0)
        except json.JSONDecodeError:
            parsed_expansion = {}

        if not isinstance(parsed_expansion, dict):
            parsed_expansion = {}

        query_expansion = {
            "key_terms": self.keep_conservative_terms(
                parsed_expansion.get("key_terms"),
                self.config["query_expansion"]["max_key_terms"]
            ),
            "acronyms": self.keep_conservative_terms(
                parsed_expansion.get("acronyms"),
                self.config["query_expansion"]["max_acronyms"]
            ),
            "variations": self.keep_conservative_terms(
                parsed_expansion.get("variations"),
                self.config["query_expansion"]["max_variations"]
            )
        }

        expanded_terms = (
            query_expansion["key_terms"]
            + query_expansion["acronyms"]
            + query_expansion["variations"]
        )
        expanded_query = " ".join([query, *expanded_terms])

        # print("\nEXPANDED QUERY TERMS")
        # print(json.dumps(query_expansion, indent=2, ensure_ascii=False))
        # print("BM25 query:", expanded_query)

        return query_expansion, expanded_query

    def rewrite_conversational_query(self, query, session):
        if not session.messages:
            return {
                "is_follow_up": False,
                "standalone_query": query,
                "status": "first_turn",
            }

        max_history_messages = self.config["conversation"]["max_history_turns"] * 2
        recent_messages = session.messages[-max_history_messages:]
        conversation_history = "\n".join(
            f"{message['role'].upper()}: {message['content']}"
            for message in recent_messages
        )
        rewrite_prompt = self.config["conversation"]["rewrite_prompt"].format(
            conversation_history=conversation_history,
            active_sources=", ".join(session.active_sources) or "None",
            query=query,
        )
        rewrite_response = self.llm.invoke(
            rewrite_prompt,
            pipeline_kwargs={
                "max_new_tokens": self.config["conversation"][
                    "rewrite_max_new_tokens"
                ]
            },
        )
        json_start = rewrite_response.find("{")

        try:
            parsed_rewrite, _ = json.JSONDecoder().raw_decode(
                rewrite_response[json_start:]
            ) if json_start != -1 else ({}, 0)
        except json.JSONDecodeError:
            parsed_rewrite = {}

        is_follow_up = parsed_rewrite.get("is_follow_up")
        standalone_query = parsed_rewrite.get("standalone_query")
        if not isinstance(is_follow_up, bool) or not isinstance(
            standalone_query, str
        ) or not standalone_query.strip():
            # A failed rewrite falls back to the user's exact message and does not
            # inherit a source restriction based on an uncertain classification.
            return {
                "is_follow_up": False,
                "standalone_query": query,
                "status": "fallback",
            }

        return {
            "is_follow_up": is_follow_up,
            "standalone_query": standalone_query.strip(),
            "status": "rewritten",
        }

    #########################################################################################################################################
    # 6- Retrieve dense and sparse candidates, then merge them
    #########################################################################################################################################
    def selected_sources(self, query, source_override=None):
        if source_override:
            unknown_sources = set(source_override) - set(self.available_sources)
            if unknown_sources:
                raise ValueError(
                    "Unknown source restriction: "
                    + ", ".join(sorted(unknown_sources))
                )
            return source_override

        explicit_sources = find_explicit_sources(query, self.available_sources)
        return explicit_sources or self.available_sources

    def retrieve_candidates(self, query, expanded_query, source_override=None):
        sources = self.selected_sources(query, source_override)

        # If a source was explicitly named, this searches only its chunks. Otherwise,
        # this searches all chunks from all sources.
        dense_results_with_scores = []
        if self.use_dense_retrieval:
            query_vector = self.embedding_model.embed_query(query)
            for source in sources:
                dense_results_with_scores.extend(
                    self.source_vector_stores[source].similarity_search_with_score_by_vector(
                        query_vector,
                        k=self.config["retrieval"]["dense_top_k"]
                    )
                )
            dense_results_with_scores.sort(key=lambda item: item[1])
            dense_results_with_scores = dense_results_with_scores[
                :self.config["retrieval"]["dense_top_k"]
            ]
        dense_candidate_docs = [doc for doc, _ in dense_results_with_scores]

        bm25_results_with_scores = []
        if self.use_bm25_retrieval:
            bm25_chunks, bm25_index = self.bm25_for_sources(sources)
            bm25_query_tokens = list(
                dict.fromkeys(self.tokenize_for_bm25(expanded_query))
            )
            bm25_scores = bm25_index.get_scores(bm25_query_tokens)
            top_bm25_indices = bm25_scores.argsort()[
                ::-1
            ][:self.config["retrieval"]["bm25_top_k"]]
            bm25_results_with_scores = [
                (bm25_chunks[index], float(bm25_scores[index]))
                for index in top_bm25_indices
                if bm25_scores[index] > self.config["retrieval"]["bm25_min_score"]
            ]
        bm25_candidate_docs = [doc for doc, _ in bm25_results_with_scores]

        """
        print("\nBM25 CANDIDATES")
        for rank, (doc, score) in enumerate(bm25_results_with_scores, start=1):
            print(
                f"{rank}. score={score:.4f} | {doc.metadata['chunk_id']} | "
                f"{doc.page_content[:200].replace(chr(10), ' ')}"
            )

        print("\nDENSE CANDIDATES")
        for rank, (doc, score) in enumerate(dense_results_with_scores, start=1):
            print(
                f"{rank}. distance={score:.4f} | {doc.metadata['chunk_id']} | "
                f"{doc.page_content[:200].replace(chr(10), ' ')}"
            )
        """

        candidate_docs = []
        candidate_methods = {}

        for retrieval_method, retrieved_docs in (
            ("dense", dense_candidate_docs),
            ("BM25", bm25_candidate_docs)
        ):
            for doc in retrieved_docs:
                chunk_id = doc.metadata["chunk_id"]

                if chunk_id not in candidate_methods:
                    candidate_docs.append(doc)
                    candidate_methods[chunk_id] = []

                candidate_methods[chunk_id].append(retrieval_method)

        """
        print("\nMERGED CANDIDATES")
        for rank, doc in enumerate(candidate_docs, start=1):
            methods = ", ".join(candidate_methods[doc.metadata["chunk_id"]])
            print(
                f"{rank}. retrieved_by={methods} | {doc.metadata['chunk_id']} | "
                f"{doc.page_content[:200].replace(chr(10), ' ')}"
            )


        Now you can print the retrieved results using:

        for i, doc in enumerate(dense_candidate_docs):

            print("=" * 80)

            print("RESULT:", i + 1)
            print("PAGE:", doc.metadata["page"])

            print(doc.page_content[:500])


        You can use dense_results_with_scores to get the score/distance of each chunk too:

        for i, (doc, score) in enumerate(dense_results_with_scores):

            print("=" * 80)

            print("Rank:", i + 1)
            print("FAISS distance:", score)
            print("Page:", doc.metadata["page"])
            print(doc.page_content[:300])

        """

        return {
            "selected_sources": sources,
            "dense_results_with_scores": dense_results_with_scores,
            "bm25_results_with_scores": bm25_results_with_scores,
            "candidate_docs": candidate_docs,
            "candidate_methods": candidate_methods,
        }

    #########################################################################################################################################
    # 7- Rerank the n candidates
    #########################################################################################################################################
    def rerank_candidates(self, query, candidate_docs, top_k=None):
        """
        the previous retrieval step is optimized for speed, not perfect relevance. FAISS quickly finds chunks whose embeddings are close to the query, but embedding similarity can still return chunks that are only loosely related.

        Reranking takes those top candidates and uses a stronger/more expensive model to score them more carefully against the actual query.
        """

        if not candidate_docs:
            return []

        if self.reranker is None:
            self.reranker = HuggingFaceCrossEncoder(
                model_name=self.config["reranking"]["model_name"]
            )

        pairs = [
            (query, doc.page_content)
            for doc in candidate_docs
        ]

        rerank_scores = self.reranker.score(pairs)

        scored_docs = list(
            zip(candidate_docs, rerank_scores)
        )

        scored_docs.sort(
            key=lambda x: x[1],
            reverse=True
        )

        reranked_docs = scored_docs[:self.config["reranking"]["final_top_k"] if top_k is None else top_k]

        """
        print("\nRERANKED RESULTS")
        for rank, (doc, score) in enumerate(reranked_docs, start=1):
            print(
                f"{rank}. score={score:.4f} | {doc.metadata['chunk_id']} | "
                f"{doc.page_content[:500].replace(chr(10), ' ')}"
            )
        """

        """
        for rank, (doc, score) in enumerate(reranked_docs, start=1):

            print("=" * 80)

            print("Reranked position:", rank)
            print("Reranker score:", score)
            print("Page:", doc.metadata["page"])

            print(doc.page_content[:500])
        """

        return reranked_docs

    #########################################################################################################################################
    # 8- Build the retrieved context
    #########################################################################################################################################
    def build_context(self, reranked_docs):
        context_parts = []
        final_chunks = []

        for rank, (doc, score) in enumerate(reranked_docs, start=1):

            source = doc.metadata["source"]
            page = doc.metadata["page"]

            context_parts.append(
                self.config["rag"]["context_entry_template"].format(
                    source=source,
                    page=page,
                    page_content=doc.page_content
                )
            )
            final_chunks.append(
                {
                    "chunk_id": doc.metadata["chunk_id"],
                    "rank": rank,
                    "reranker_score": float(score),
                    "source": source,
                    "page": page,
                    "start_index": doc.metadata["start_index"],
                    "text": doc.page_content,
                }
            )

        context = self.config["rag"]["context_separator"].join(context_parts)

        # print(context)
        return context, final_chunks

    def retrieve_and_rerank_context(
        self,
        query,
        expanded_query,
        source_override=None,
    ):
        retrieval = self.retrieve_candidates(
            query,
            expanded_query,
            source_override,
        )
        reranked_docs = self.rerank_candidates(
            query,
            retrieval["candidate_docs"]
        )
        context, final_chunks = self.build_context(reranked_docs)

        return {
            "selected_sources": retrieval["selected_sources"],
            "context": context,
            "final_chunks": final_chunks,
        }

    #########################################################################################################################################
    # 9- Construct the actual RAG prompt
    #########################################################################################################################################
    def build_prompt(self, context, query, prompt_template=None):
        rag_prompt = PromptTemplate.from_template(
            prompt_template or self.config["rag"]["prompt"]
        )

        formatted_prompt = rag_prompt.format(
            context=context,
            question=query
        )

        # print(formatted_prompt)
        return formatted_prompt

    def build_related_problem_prompt(
        self,
        technical_context,
        leetcode_context,
        query,
        conceptual_assessments=None,
    ):
        related_problem_prompt = PromptTemplate.from_template(
            self.config["related_problem"]["prompt"]
        )

        return related_problem_prompt.format(
            technical_context=technical_context,
            leetcode_context=leetcode_context,
            question=query,
            conceptual_assessments=json.dumps(conceptual_assessments or [], ensure_ascii=False),
        )

    #########################################################################################################################################
    # 10- Generate the grounded response with the already-loaded LLM
    #########################################################################################################################################
    def generate_answer(self, formatted_prompt):
        return self.llm.invoke(formatted_prompt)

    def run(self, query, source_override=None, prompt_template=None):
        query_expansion = {
            "key_terms": [],
            "acronyms": [],
            "variations": [],
        }
        expanded_query = query
        if self.use_bm25_retrieval and self.use_query_expansion:
            query_expansion, expanded_query = self.expand_query(query)

        retrieval = self.retrieve_and_rerank_context(
            query,
            expanded_query,
            source_override,
        )
        formatted_prompt = self.build_prompt(
            retrieval["context"],
            query,
            prompt_template,
        )
        response = self.generate_answer(formatted_prompt)

        return {
            "selected_sources": retrieval["selected_sources"],
            "explicit_source_restriction_detected": bool(
                find_explicit_sources(query, self.available_sources)
            ),
            "query_expansion": query_expansion,
            "final_context": retrieval["context"],
            "final_chunks": retrieval["final_chunks"],
            "generated_answer": response,
        }

    #########################################################################################################################################
    # Related-problem workflow: retrieve technical evidence and LeetCode candidates independently
    #########################################################################################################################################
    def extract_transferable_patterns(self, query, technical_context, technical_chunks):
        settings = self.config["related_problem"]["pattern_extraction"]
        fallback = {
            "topic": query,
            "source_terms": [],
            "transferable_patterns": [],
            "leetcode_search_query": query,
            "status": "fallback",
            "verification_notes": "No technical evidence was retrieved.",
            "rejected_items": [],
        }
        if not technical_chunks:
            return fallback

        # Passage IDs are local to this extraction; Python owns their source/page mapping.
        passages = {f"P{index}": chunk for index, chunk in enumerate(technical_chunks, start=1)}
        technical_context = "\n\n".join(
            f"PASSAGE_ID: {passage_id}\nSOURCE: {chunk['source']}\nPAGE: {chunk['page']}\n{chunk['text']}"
            for passage_id, chunk in passages.items()
        )
        base_prompt = settings["prompt"].format(
            question=query,
            technical_context=technical_context,
            max_source_terms=settings["max_source_terms"],
            max_patterns=settings["max_patterns"],
            max_query_length=settings["max_query_length"],
            min_quote_words=settings["min_quote_words"],
            max_quote_words=settings["max_quote_words"],
        )
        # Read the first JSON object, as in query expansion. A quote match checks
        # provenance, not whether the model's proposed conceptual link is correct.
        def normalize(text):
            text = unicodedata.normalize("NFKC", text)
            text = re.sub(r"(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)", "", text)
            return " ".join(text.split())

        evidence_texts = [normalize(chunk["text"]) for chunk in technical_chunks]
        terms, inferred_patterns, rejected_items = [], [], []
        quote_repairs = {}
        feedback = ""
        # One corrective retry helps Qwen repair formatting or copying errors.
        for attempt in range(2):
            # Qwen-Instruct expects chat formatting for reliable instruction following.
            prompt = self.llm.pipeline.tokenizer.apply_chat_template(
                [{"role": "user", "content": base_prompt + feedback}],
                tokenize=False,
                add_generation_prompt=True,
            )
            response = self.llm.invoke(
                prompt,
                pipeline_kwargs={"max_new_tokens": settings["max_new_tokens"]},
            )
            errors = []
            quote_failures = []
            try:
                json_start = response.find("{")
                if json_start == -1:
                    raise ValueError("No JSON object was returned.")
                patterns, _ = json.JSONDecoder().raw_decode(response[json_start:])
                if not isinstance(patterns, dict):
                    raise ValueError("The extraction must be a JSON object.")
                if patterns.get("evidence_sufficient") is False:
                    fallback["verification_notes"] = "Qwen reported insufficient evidence for the requested topic."
                    fallback["rejected_items"] = rejected_items
                    return fallback
                if patterns.get("evidence_sufficient") is not True:
                    raise ValueError("Missing boolean evidence_sufficient; assess relevance to the REQUEST first.")
                proposed_terms = patterns.get("source_terms")
                if not isinstance(proposed_terms, list):
                    errors.append("source_terms must be a list.")
                    proposed_terms = []
                for term in proposed_terms:
                    if not isinstance(term, str) or not term.strip() or not any(
                        normalize(term) in text for text in evidence_texts
                    ):
                        errors.append(f"Rejected source term {term!r}: not a literal term in the evidence; copy its exact wording or omit it.")
                    elif term.strip() not in terms and len(terms) < settings["max_source_terms"]:
                        terms.append(term.strip())
                proposed_patterns = patterns.get("transferable_patterns")
                if not isinstance(proposed_patterns, list):
                    errors.append("transferable_patterns must be a list.")
                    proposed_patterns = []
                for pattern in proposed_patterns[:settings["max_patterns"]]:
                    fields = ("pattern", "reason", "topic_connection", "passage_id", "supporting_quote", "coding_task")
                    if not isinstance(pattern, dict) or any(
                        not isinstance(pattern.get(field), str) or not pattern[field].strip()
                        for field in fields
                    ):
                        errors.append(f"Rejected pattern {pattern!r}: each pattern needs nonempty {fields}.")
                        continue
                    passage_id = pattern["passage_id"].strip()
                    if passage_id not in passages:
                        errors.append(f"Rejected passage_id {passage_id!r}: select one of {list(passages)}; do not invent an ID.")
                        continue
                    passage = passages[passage_id]
                    passage_text = normalize(passage["text"])
                    quote = normalize(pattern["supporting_quote"])
                    if quote not in passage_text:
                        # Offer only literal, already-matching fragments, never a fuzzy match.
                        # Qwen must still decide whether a fragment supports this pattern.
                        words = quote.split()
                        # Prefer complete short clauses over arbitrary, cut-off windows.
                        examples = sorted({
                            excerpt for excerpt in re.split(r"(?<=[,;.!?])\s+", quote)
                            if settings["min_quote_words"] <= len(excerpt.split()) <= settings["max_quote_words"]
                            and excerpt in passage_text
                        }, key=lambda excerpt: (-len(excerpt.split()), excerpt))[:2]
                        for size in ([] if examples else range(min(len(words), settings["max_quote_words"]), settings["min_quote_words"] - 1, -1)):
                            for start in range(len(words) - size + 1):
                                excerpt = " ".join(words[start:start + size])
                                if excerpt not in examples and excerpt in passage_text:
                                    examples.append(excerpt)
                                    if len(examples) == 2:
                                        break
                            if examples:
                                break
                        error = f"Rejected quote {pattern['supporting_quote']!r} for pattern {pattern['pattern']!r}: not consecutive text in {passage_id}. Literal excerpt options (use only if relevant): {examples!r}."
                        repair_key = (passage_id, quote)
                        if repair_key not in quote_repairs:
                            # A quote gets one focused retry with ONLY its selected passage.
                            quote_options = {f"Q{index}": excerpt for index, excerpt in enumerate(examples, start=1)}
                            retry_prompt = settings["quote_retry_prompt"].format(
                                question=query,
                                pattern=json.dumps(pattern, ensure_ascii=False),
                                error=error,
                                passage_id=passage_id,
                                passage_text=passage["text"],
                                quote_options=json.dumps(quote_options, ensure_ascii=False),
                                min_quote_words=settings["min_quote_words"],
                                max_quote_words=settings["max_quote_words"],
                            )
                            retry_prompt = self.llm.pipeline.tokenizer.apply_chat_template(
                                [{"role": "user", "content": retry_prompt}],
                                tokenize=False,
                                add_generation_prompt=True,
                            )
                            retry_response = self.llm.invoke(
                                retry_prompt,
                                pipeline_kwargs={"max_new_tokens": settings["quote_retry_max_new_tokens"]},
                            )
                            try:
                                json_start = retry_response.find("{")
                                if json_start == -1:
                                    raise ValueError("Quote retry returned no JSON object.")
                                repaired, _ = json.JSONDecoder().raw_decode(retry_response[json_start:])
                                repaired_quote = repaired.get("supporting_quote") if isinstance(repaired, dict) else None
                                if isinstance(repaired, dict) and "quote_option" in repaired:
                                    option = repaired["quote_option"]
                                    if not isinstance(option, str) or option not in quote_options:
                                        raise ValueError("Quote retry selected no valid literal excerpt option.")
                                    # Python copies the literal excerpt, so Qwen need not retype it.
                                    repaired_quote = quote_options[option]
                                if not isinstance(repaired_quote, str) or not repaired_quote.strip() or normalize(repaired_quote) not in passage_text:
                                    raise ValueError("Retried quote is empty or does not occur in the selected passage.")
                                quote_repairs[repair_key] = (repaired_quote.strip(), None)
                            except (json.JSONDecodeError, ValueError) as retry_error:
                                quote_repairs[repair_key] = (None, str(retry_error))
                        repaired_quote, retry_error = quote_repairs[repair_key]
                        rejected_items.append({
                            "attempt": attempt + 1,
                            "error": error,
                            "passage_id": passage_id,
                            "quote_retry_status": "failed" if retry_error else "repaired",
                            "quote_retry_error": retry_error,
                        })
                        if retry_error:
                            quote_failures.append(error)
                            continue
                        pattern = {**pattern, "supporting_quote": repaired_quote}
                    if len(pattern["coding_task"].strip()) > settings["max_query_length"]:
                        errors.append(f"Rejected coding_task {pattern['coding_task']!r}: exceeds {settings['max_query_length']} characters.")
                        continue
                    accepted = {field: pattern[field].strip() for field in fields}
                    accepted.update(source=passage["source"], page=passage["page"], chunk_id=passage["chunk_id"])
                    if accepted not in inferred_patterns and len(inferred_patterns) < settings["max_patterns"]:
                        inferred_patterns.append(accepted)
                if not inferred_patterns and not quote_failures:
                    errors.append("No accepted patterns yet. Repair the rejected items; report evidence_sufficient=false ONLY if the evidence itself is insufficient or unrelated.")
            except (json.JSONDecodeError, ValueError) as error:
                errors.append(str(error))
            rejected_items.extend({"attempt": attempt + 1, "error": error} for error in errors)
            if not errors:
                break
            feedback = (
                "\nCORRECTION: Fix ONLY these rejected items, or omit them:\n"
                + json.dumps(errors, ensure_ascii=False)
                + "\nPreviously accepted patterns will be retained; do not repeat them:\n"
                + json.dumps(inferred_patterns, ensure_ascii=False)
                + "\nQuote-formatting errors do not imply insufficient evidence. Return complete JSON. Do not invent a relationship to the request."
            )

        if not inferred_patterns:
            fallback["verification_notes"] = "No usable patterns remained after verification and bounded retries."
            fallback["rejected_items"] = rejected_items
            return fallback

        # Never reuse a model-wide query that might depend on rejected patterns.
        # Assemble complete coding tasks only from individually accepted patterns.
        tasks = []
        for pattern in inferred_patterns:
            task = pattern["coding_task"]
            if task not in tasks and len("; ".join(tasks + [task])) <= settings["max_query_length"]:
                tasks.append(task)

        return {
            "topic": query,
            "source_terms": terms,
            "transferable_patterns": inferred_patterns,
            "leetcode_search_query": "; ".join(tasks),
            "status": "extracted",
            "verification_notes": "Accepted source terms and quotes matched normalized text; topic connections remain model inferences, not verified relevance judgments.",
            "rejected_items": rejected_items,
        }

    def build_leetcode_search_queries(self, pattern_extraction):
        settings = self.config["related_problem"]["candidate_retrieval"]
        baseline = {
            "queries": [{"pattern_index": None, "query": pattern_extraction["leetcode_search_query"]}],
            "status": "baseline",
            "notes": [],
        }
        if pattern_extraction["status"] != "extracted":
            return baseline

        # Only accepted patterns reach this pass; rejected items and raw history do not.
        patterns = pattern_extraction["transferable_patterns"]
        prompt = settings["prompt"].format(
            patterns=json.dumps([
                {"pattern_index": index, **{field: pattern[field] for field in (
                    "pattern", "reason", "topic_connection", "supporting_quote"
                )}}
                for index, pattern in enumerate(patterns, start=1)
            ], ensure_ascii=False),
            max_queries=settings["max_queries"],
            max_query_length=settings["max_query_length"],
        )
        prompt = self.llm.pipeline.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True,
        )
        response = self.llm.invoke(
            prompt, pipeline_kwargs={"max_new_tokens": settings["max_new_tokens"]},
        )
        queries, notes, seen = [], [], set()
        try:
            json_start = response.find("{")
            if json_start == -1:
                raise ValueError("No query-plan JSON object was returned.")
            plan, _ = json.JSONDecoder().raw_decode(response[json_start:])
            if not isinstance(plan, dict) or not isinstance(plan.get("queries"), list):
                raise ValueError("The query plan needs a queries list.")
            for entry in plan["queries"]:
                if not isinstance(entry, dict):
                    notes.append(f"Rejected query entry: {entry!r}.")
                    continue
                index, search_query = entry.get("pattern_index"), entry.get("query")
                if type(index) is not int or not 1 <= index <= len(patterns):
                    notes.append(f"Rejected pattern_index {index!r}: no such accepted pattern.")
                    continue
                if not isinstance(search_query, str) or not search_query.strip() or len(search_query.strip()) > settings["max_query_length"]:
                    notes.append(f"Rejected empty, non-text, or overlong query: {search_query!r}.")
                    continue
                search_query = " ".join(search_query.split())
                # Synthetic example numbers can pull retrieval toward unrelated tasks.
                pattern_text = " ".join(patterns[index - 1][field] for field in (
                    "pattern", "reason", "topic_connection", "supporting_quote"
                ))
                query_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", search_query))
                supported_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", pattern_text))
                if query_numbers - supported_numbers:
                    notes.append(f"Rejected query with invented numerical inputs: {search_query!r}.")
                    continue
                if search_query.casefold() not in seen and len(queries) < settings["max_queries"]:
                    queries.append({"pattern_index": index, "query": search_query})
                    seen.add(search_query.casefold())
        except (json.JSONDecodeError, ValueError) as error:
            notes.append(str(error))
        if not queries:
            return {**baseline, "status": "fallback", "notes": notes + ["Using the existing coding-task bridge query."]}
        return {"queries": queries, "status": "generated", "notes": notes}

    def extract_related_relationship(self, pattern_extraction, technical_chunks):
        settings = self.config["related_problem"]["conceptual_reranking"]
        patterns = pattern_extraction["transferable_patterns"]
        passages = {chunk["chunk_id"]: chunk for chunk in technical_chunks}

        def normalize(text):
            text = unicodedata.normalize("NFKC", text)
            text = re.sub(r"(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)", "", text)
            return " ".join(text.split())

        # Keep the actual technical passage beside each pattern, not just its short quote.
        # Quote occurrence verifies provenance; conceptual relevance is still Qwen's judgment.
        # Read the original prose, not generated coding tasks or inferred mechanisms.
        # These passages already came from topic retrieval; the procedural question is not re-fed here.
        selected_passages = list({pattern["chunk_id"]: passages[pattern["chunk_id"]] for pattern in patterns}.values())
        outcome = {"status": "skipped_no_patterns", "attempts": []}
        if not selected_passages:
            return outcome
        base_prompt = settings["relationship_prompt"].format(
            passages="\n\n".join(passage["text"] for passage in selected_passages),
        )
        feedback = ""
        for attempt in range(2):
            prompt = self.llm.pipeline.tokenizer.apply_chat_template(
                [{"role": "user", "content": base_prompt + feedback}],
                tokenize=False, add_generation_prompt=True,
            )
            response = self.llm.invoke(
                prompt, pipeline_kwargs={"max_new_tokens": settings["relationship_max_new_tokens"]},
            )
            try:
                start = response.find("{")
                if start == -1:
                    raise ValueError("No relationship JSON object was returned.")
                result, _ = json.JSONDecoder().raw_decode(response[start:])
                if not isinstance(result, dict) or "relationship" not in result:
                    raise ValueError("Return a relationship string, or null if the prose is insufficient.")
                if not isinstance(result.get("explanation"), str) or not result["explanation"].strip():
                    raise ValueError("Provide a nonempty explanation.")
                if result["relationship"] is not None:
                    for field in ("relationship", "technical_quote"):
                        if not isinstance(result.get(field), str) or not result[field].strip():
                            raise ValueError(f"Provide a nonempty {field}.")
                    quote = normalize(result["technical_quote"])
                    matches = [passage for passage in selected_passages if quote in normalize(passage["text"])]
                    if len(quote.split()) < 3 or len(matches) != 1:
                        raise ValueError(f"technical_quote {result['technical_quote']!r} must match at least three consecutive words in exactly one supplied passage (found {len(matches)} matches). Copy a longer literal quote if ambiguous.")
                    passage = matches[0]
                    outcome.update(
                        status="extracted", relationship=result["relationship"].strip(),
                        technical_quote=result["technical_quote"].strip(),
                        technical_evidence={key: passage[key] for key in ("chunk_id", "source", "page")},
                    )
                else:
                    outcome["status"] = "insufficient_evidence"
                outcome["explanation"] = result["explanation"].strip()
                outcome["attempts"].append({"attempt": attempt + 1, "response": response, "error": None})
                break
            except (json.JSONDecodeError, ValueError) as error:
                outcome["status"] = "unscored"
                outcome["attempts"].append({"attempt": attempt + 1, "response": response, "error": str(error)})
                feedback = "\nCORRECTION: " + str(error) + " Return complete JSON; copy a short literal quote or report insufficient evidence."
        return outcome

    def isolate_related_problems(self, shortlisted_docs):
        settings = self.config["related_problem"]["problem_isolation"]
        groups, notes = {}, []
        # Only query-time processing: indexes, retrieval, and original chunk IDs stay unchanged.
        # Saved page text recovers a heading even when the retrieved chunk begins mid-problem.
        for doc, score in shortlisted_docs:
            source, page = doc.metadata["source"], doc.metadata["page"]
            text = self.page_texts.get((source, page))
            start = doc.metadata.get("start_index")
            error = None
            if text is None:
                error = "Saved source page text is unavailable."
            elif type(start) is not int or start < 0 or text[start:start + len(doc.page_content)] != doc.page_content:
                error = "The chunk does not match its recorded character span in the saved source page."
            headers = list(re.finditer(settings["header_pattern"], text)) if error is None else []
            ranges = list(re.finditer(settings["page_range_pattern"], text)) if error is None else []
            numbers = [int(match["number"]) for match in headers]
            first, last = (int(ranges[0]["first"]), int(ranges[0]["last"] or ranges[0]["first"])) if len(ranges) == 1 else (None, None)
            if error is None and (not headers or len(ranges) != 1 or len(set(numbers)) != len(numbers)
                                  or len(headers) != last - first + 1
                                  or min(numbers) != first or max(numbers) != last):
                error = "Problem headings are missing or ambiguous on this page."
            if error:
                notes.append({"chunk_id": doc.metadata["chunk_id"], "source": source, "page": page,
                              "status": "unscored_problem_isolation", "note": error, "attempts": []})
                continue
            footer = re.search(settings["footer_pattern"], text)
            found_body = False
            for index, header in enumerate(headers):
                end = headers[index + 1].start() if index + 1 < len(headers) else (footer.start() if footer else len(text))
                left, right = max(start, header.end()), min(start + len(doc.page_content), end)
                body = text[left:right] if left < right else ""
                if not body.strip():
                    continue
                left += len(body) - len(body.lstrip())
                right = left + len(body.strip())
                found_body = True
                problem_id = f"{source}::page={page}::problem={header['number']}"
                if problem_id not in groups:
                    groups[problem_id] = {
                        "metadata": {**doc.metadata, "problem_id": problem_id,
                                     "problem_identity": {"number": int(header["number"]), "title": " ".join(header["title"].split()),
                                                          "difficulty": header["difficulty"], "heading_quote": header.group().strip()},
                                     "parent_chunk_ids": []},
                        "score": float(score), "spans": [],
                    }
                group = groups[problem_id]
                group["spans"].append((left, right))
                if doc.metadata["chunk_id"] not in group["metadata"]["parent_chunk_ids"]:
                    group["metadata"]["parent_chunk_ids"].append(doc.metadata["chunk_id"])
                if float(score) > group["score"]:
                    group["score"] = float(score)
                    group["metadata"]["chunk_id"] = doc.metadata["chunk_id"]
            if not found_body:
                notes.append({"chunk_id": doc.metadata["chunk_id"], "source": source, "page": page,
                              "status": "unscored_problem_isolation", "note": "No identified problem prose overlaps this chunk.", "attempts": []})

        problem_docs = []
        for group in groups.values():
            metadata = group["metadata"]
            spans = []
            for left, right in sorted(group["spans"]):
                if spans and left <= spans[-1][1]:
                    spans[-1] = (spans[-1][0], max(spans[-1][1], right))
                else:
                    spans.append((left, right))
            # Merge overlapping retrieved coverage, but never silently fill an unretrieved gap.
            page_text = self.page_texts[(metadata["source"], metadata["page"])]
            excerpts = [page_text[left:right] for left, right in spans]
            metadata.update(start_index=spans[0][0], problem_excerpts=excerpts,
                            problem_spans=[{"start": left, "end": right} for left, right in spans])
            problem_docs.append((Document(page_content="\n\n[Unretrieved gap]\n\n".join(excerpts), metadata=metadata), group["score"]))
        return problem_docs, notes

    def rerank_related_candidates(self, query, pattern_extraction, technical_chunks, shortlisted_docs):
        settings = self.config["related_problem"]["conceptual_reranking"]
        problem_docs, isolation_notes = self.isolate_related_problems(shortlisted_docs)
        relationship = self.extract_related_relationship(pattern_extraction, technical_chunks) if problem_docs else {
            "status": "skipped_no_candidates", "attempts": [],
        }
        passages = {chunk["chunk_id"]: chunk for chunk in technical_chunks}
        judgments, accepted = isolation_notes, []

        def normalize(text):
            text = unicodedata.normalize("NFKC", text)
            text = re.sub(r"(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)", "", text)
            return " ".join(text.split())

        # No numeric rating: a chunk either supports this specific relationship or does not.
        # Each candidate is now ONE problem's retrieved prose, not an entire mixed-problem chunk.
        labels = ("supported_match", "weak_match", "unrelated")
        for rank, (doc, cross_encoder_score) in enumerate(problem_docs, start=1):
            judgment = {
                "chunk_id": doc.metadata["chunk_id"], "source": doc.metadata["source"],
                "page": doc.metadata["page"], "shortlist_rank": rank,
                "cross_encoder_score": float(cross_encoder_score), "attempts": [],
                "problem_id": doc.metadata["problem_id"], "problem_identity": doc.metadata["problem_identity"],
                "parent_chunk_ids": doc.metadata["parent_chunk_ids"], "problem_text": doc.page_content,
            }
            if relationship["status"] != "extracted":
                judgments.append({**judgment, "status": "skipped_no_relationship",
                                  "note": "No usable technical relationship; no conceptual recommendation is supported."})
                continue
            base_prompt = settings["prompt"].format(
                relationship=relationship["relationship"], candidate_text=doc.page_content,
            )
            feedback = ""
            # One call per candidate, with one bounded corrective retry if invalid.
            for attempt in range(2):
                prompt = self.llm.pipeline.tokenizer.apply_chat_template(
                    [{"role": "user", "content": base_prompt + feedback}],
                    tokenize=False, add_generation_prompt=True,
                )
                response = self.llm.invoke(
                    prompt, pipeline_kwargs={"max_new_tokens": settings["max_new_tokens"]},
                )
                try:
                    json_start = response.find("{")
                    if json_start == -1:
                        raise ValueError("No JSON object was returned.")
                    result, _ = json.JSONDecoder().raw_decode(response[json_start:])
                    if not isinstance(result, dict) or result.get("match_label") not in labels:
                        raise ValueError("match_label must be supported_match, weak_match, or unrelated.")
                    assessment = {"match_label": result["match_label"]}
                    for field in ("candidate_relationship", "explanation"):
                        if not isinstance(result.get(field), str) or not result[field].strip():
                            raise ValueError(f"Provide a nonempty {field}.")
                        assessment[field] = result[field].strip()
                    if result["match_label"] == "supported_match":
                        for field in ("leetcode_quote",):
                            if not isinstance(result.get(field), str) or not result[field].strip():
                                raise ValueError(f"Missing nonempty {field} for a supported match.")
                            assessment[field] = result[field].strip()
                        quote = normalize(assessment["leetcode_quote"])
                        if len(quote.split()) < 3 or not any(quote in normalize(excerpt) for excerpt in doc.metadata["problem_excerpts"]):
                            raise ValueError(f"leetcode_quote {assessment['leetcode_quote']!r} must match at least three consecutive words in the supplied chunk body.")
                        # Python owns the chunk IDs and citations, never generated IDs/pages.
                        assessment.update(
                            shared_mechanism=relationship["relationship"],
                            technical_relationship=relationship["relationship"],
                            technical_quote=relationship["technical_quote"],
                            technical_evidence=relationship["technical_evidence"],
                        )
                    judgment["attempts"].append({"attempt": attempt + 1, "response": response, "error": None})
                    judgment.update(assessment, status="rejected")
                    break
                except (json.JSONDecodeError, ValueError) as error:
                    judgment["attempts"].append({"attempt": attempt + 1, "response": response, "error": str(error)})
                    judgment["status"] = "unscored"
                    feedback = "\nCORRECTION: " + str(error) + " Return complete JSON. Copy a short literal quote; do not invent support."

            if judgment.get("match_label") == "supported_match":
                # A separate call checks the claim against BOTH original passages.
                # It does not see the candidate judge's label, explanation, or numeric score.
                technical_passage = passages[relationship["technical_evidence"]["chunk_id"]]
                base_prompt = settings["verification_prompt"].format(
                    relationship=relationship["relationship"], technical_text=technical_passage["text"],
                    candidate_text=doc.page_content, technical_quote=relationship["technical_quote"],
                    leetcode_quote=judgment["leetcode_quote"],
                )
                verification = {"status": "unscored", "attempts": []}
                feedback = ""
                for attempt in range(2):
                    prompt = self.llm.pipeline.tokenizer.apply_chat_template(
                        [{"role": "user", "content": base_prompt + feedback}],
                        tokenize=False, add_generation_prompt=True,
                    )
                    response = self.llm.invoke(
                        prompt, pipeline_kwargs={"max_new_tokens": settings["verification_max_new_tokens"]},
                    )
                    try:
                        start = response.find("{")
                        if start == -1:
                            raise ValueError("No verification JSON object was returned.")
                        result, _ = json.JSONDecoder().raw_decode(response[start:])
                        if not isinstance(result, dict) or type(result.get("supported")) is not bool:
                            raise ValueError("supported must be a boolean.")
                        if not isinstance(result.get("explanation"), str) or not result["explanation"].strip():
                            raise ValueError("Provide a nonempty verification explanation.")
                        if result["supported"]:
                            difference = result.get("important_difference")
                            if not isinstance(difference, str) or not difference.strip():
                                raise ValueError("For supported=true, explain an important_difference between the technical passage and the ONE selected coding problem.")
                            judgment["important_difference"] = difference.strip()
                        verification.update(status="valid", supported=result["supported"], explanation=result["explanation"].strip())
                        verification["attempts"].append({"attempt": attempt + 1, "response": response, "error": None})
                        judgment["status"] = "accepted" if result["supported"] else "rejected"
                        if result["supported"]:
                            accepted.append((doc, cross_encoder_score))
                        break
                    except (json.JSONDecodeError, ValueError) as error:
                        verification["attempts"].append({"attempt": attempt + 1, "response": response, "error": str(error)})
                        judgment["status"] = "unscored"
                        feedback = "\nCORRECTION: " + str(error) + " Return ONLY complete JSON with supported and explanation."
                judgment["verification"] = verification
            judgments.append(judgment)

        # Previously, ordinal ratings ranked links:
        # Stronger conceptual links first; the cross-encoder breaks ties.
        # Now every retained link passed both checks; keep cross-encoder order within that set.
        accepted.sort(key=lambda item: float(item[1]), reverse=True)
        selected = accepted[:self.config["reranking"]["final_top_k"]]
        selected_ids = {doc.metadata["problem_id"] for doc, _ in selected}
        for judgment in judgments:
            judgment["selected_for_context"] = judgment.get("problem_id") in selected_ids
        return selected, judgments, relationship

    def generate_related_recommendations(self, formatted_prompt, selected_judgments):
        settings = self.config["related_problem"]["recommendation_validation"]
        if type(settings["max_recommendations"]) is not int or settings["max_recommendations"] < 1:
            raise ValueError("related_problem.recommendation_validation.max_recommendations must be a positive integer.")
        accepted, attempts, rejected = {}, [], []
        feedback = ""

        def normalize(text):
            return " ".join(unicodedata.normalize("NFKC", text).split())

        # The LLM may propose identities; only exact source-verified identities can be displayed.
        # Python renders titles, difficulty, and citations from the selected source records.
        for attempt in range(2):
            prompt = self.llm.pipeline.tokenizer.apply_chat_template(
                [{"role": "user", "content": formatted_prompt + feedback}], tokenize=False, add_generation_prompt=True,
            )
            response = self.llm.invoke(prompt, pipeline_kwargs={"max_new_tokens": settings["max_new_tokens"]})
            errors = []
            try:
                start = min((position for position in (response.find("{"), response.find("[")) if position != -1), default=-1)
                if start == -1:
                    raise ValueError("No recommendation JSON was returned.")
                result, _ = json.JSONDecoder().raw_decode(response[start:])
                # A bare JSON array is harmless; every proposed identity still gets the same strict checks.
                recommendations = result if isinstance(result, list) else result.get("recommendations") if isinstance(result, dict) else None
                if not isinstance(recommendations, list):
                    raise ValueError("Return a recommendations list.")
                for item in recommendations:
                    index = item.get("candidate_index") if isinstance(item, dict) else None
                    if type(index) is not int or not 1 <= index <= len(selected_judgments):
                        errors.append(f"Unknown candidate_index: {index!r}.")
                        rejected.append({"attempt": attempt + 1, "item": item, "error": errors[-1]})
                        continue
                    judgment = selected_judgments[index - 1]
                    identity = judgment["problem_identity"]
                    if (type(item.get("number")) is not int or item["number"] != identity["number"]
                            or any(not isinstance(item.get(field), str) or normalize(item[field]) != normalize(identity[field])
                                   for field in ("title", "difficulty"))):
                        errors.append(f"candidate_index {index}: copy exactly number={identity['number']}, title={identity['title']!r}, difficulty={identity['difficulty']!r}.")
                        rejected.append({"attempt": attempt + 1, "item": item, "error": errors[-1]})
                        continue
                    if index not in accepted and len(accepted) < settings["max_recommendations"]:
                        accepted[index] = judgment
            except (json.JSONDecodeError, ValueError) as error:
                errors.append(str(error))
            attempts.append({"attempt": attempt + 1, "response": response, "errors": errors})
            if not errors:
                break
            feedback = "\nCORRECTION: " + " ".join(errors) + " Return complete recommendations JSON using only the supplied verified identities. Do not invent missing details."

        blocks = []
        for judgment in accepted.values():
            identity, technical = judgment["problem_identity"], judgment["technical_evidence"]
            blocks.append(
                f"{identity['number']}. {identity['title']} ({identity['difficulty']})\n"
                f"Shared condition: {judgment['shared_mechanism']}\n"
                f"Important difference: {judgment['important_difference']}\n"
                f"Technical quote: {judgment['technical_quote']}\n"
                f"Problem quote: {judgment['leetcode_quote']}\n"
                f"SOURCES: {technical['source']}, PAGE: {technical['page']}; {judgment['source']}, PAGE: {judgment['page']}"
            )
        response = "\n\n".join(blocks) if blocks else "No source-verified recommendation was selected; no problem details have been guessed."
        return response, {"status": "validated" if blocks else "no_valid_recommendations", "attempts": attempts,
                          "rejected_items": rejected, "accepted_problem_ids": [judgment["problem_id"] for judgment in accepted.values()]}

    def run_related_problem(self, query):
        shortlist_top_k = self.config["related_problem"]["conceptual_reranking"]["shortlist_top_k"]
        if type(shortlist_top_k) is not int or shortlist_top_k < 1:
            raise ValueError("related_problem.conceptual_reranking.shortlist_top_k must be a positive integer.")
        leetcode_source = self.config["related_problem"]["source"]
        explicit_sources = find_explicit_sources(
            query,
            self.available_sources,
        )
        explicitly_selected_technical_sources = [
            source
            for source in explicit_sources
            if source != leetcode_source
        ]
        technical_sources = explicitly_selected_technical_sources or [
            source
            for source in self.available_sources
            if source != leetcode_source
        ]

        if not technical_sources:
            raise ValueError(
                "The related-problem workflow requires at least one "
                "non-LeetCode source for technical evidence."
            )

        query_expansion = {
            "key_terms": [],
            "acronyms": [],
            "variations": [],
        }
        expanded_query = query
        if self.use_bm25_retrieval and self.use_query_expansion:
            query_expansion, expanded_query = self.expand_query(query)

        # Technical evidence is retrieved independently from the LeetCode
        # candidates so that each stage remains visible and testable.
        technical_retrieval = self.retrieve_and_rerank_context(
            query,
            expanded_query,
            source_override=technical_sources,
        )
        pattern_extraction = self.extract_transferable_patterns(
            query,
            technical_retrieval["context"],
            technical_retrieval["final_chunks"],
        )
        leetcode_query_plan = self.build_leetcode_search_queries(pattern_extraction)
        candidate_docs, candidate_queries, retrieval_runs = {}, {}, []
        # Dense retrieval and reranking use the bridge query; BM25 also receives
        # its optional conservative expansion. A failed extraction keeps the baseline.
        # Multiple task queries broaden the pool BEFORE the existing reranker.
        for query_index, search in enumerate(leetcode_query_plan["queries"], start=1):
            search_query = search["query"]
            expansion = {"key_terms": [], "acronyms": [], "variations": []}
            expanded_search = search_query
            if leetcode_query_plan["status"] == "baseline":
                expansion, expanded_search = query_expansion, expanded_query
            elif self.use_bm25_retrieval and self.use_query_expansion:
                expansion, expanded_search = self.expand_query(search_query)
            retrieved = self.retrieve_candidates(
                search_query, expanded_search, source_override=[leetcode_source],
            )
            retrieval_runs.append({
                **search,
                "query_expansion": expansion,
                "dense_chunk_ids": [doc.metadata["chunk_id"] for doc, _ in retrieved["dense_results_with_scores"]],
                "bm25_chunk_ids": [doc.metadata["chunk_id"] for doc, _ in retrieved["bm25_results_with_scores"]],
            })
            for doc in retrieved["candidate_docs"]:
                chunk_id = doc.metadata["chunk_id"]
                candidate_docs[chunk_id] = doc
                candidate_queries.setdefault(chunk_id, []).append({
                    "query_index": query_index,
                    "methods": retrieved["candidate_methods"][chunk_id],
                })
        leetcode_query = "; ".join(search["query"] for search in leetcode_query_plan["queries"])
        shortlisted_docs = self.rerank_candidates(
            leetcode_query, list(candidate_docs.values()),
            top_k=shortlist_top_k,
        )
        _, shortlisted_chunks = self.build_context(shortlisted_docs)
        conceptually_ranked_docs, conceptual_judgments, relationship_extraction = self.rerank_related_candidates(
            query, pattern_extraction, technical_retrieval["final_chunks"], shortlisted_docs,
        )
        context, final_chunks = self.build_context(conceptually_ranked_docs)
        for chunk, (doc, _) in zip(final_chunks, conceptually_ranked_docs):
            chunk.update({key: doc.metadata[key] for key in (
                "problem_id", "problem_identity", "parent_chunk_ids", "problem_spans", "problem_excerpts"
            )})
        leetcode_retrieval = {
            "selected_sources": [leetcode_source], "context": context, "final_chunks": final_chunks,
        }

        selected_judgments = [
            {"candidate_index": index, **{key: value for key, value in judgment.items()
                                          if key not in ("attempts", "verification")}}
            for index, judgment in enumerate(
                [judgment for judgment in conceptual_judgments if judgment["selected_for_context"]], start=1,
            )
        ]
        formatted_prompt = self.build_related_problem_prompt(
            technical_retrieval["context"],
            leetcode_retrieval["context"],
            query,
            selected_judgments,
        )
        # Do not ask the answer model to fill in a recommendation after the gate rejects everything.
        if final_chunks:
            response, recommendation_validation = self.generate_related_recommendations(formatted_prompt, selected_judgments)
        else:
            response = (
                "No related LeetCode recommendation is supported by the current retrieved evidence: "
                "no candidate passed conceptual reranking. See the extraction and judgment diagnostics."
            )
            recommendation_validation = {"status": "skipped_no_candidates", "attempts": [], "rejected_items": [], "accepted_problem_ids": []}

        technical_chunks = [
            {
                **chunk,
                "context_role": "technical_evidence",
            }
            for chunk in technical_retrieval["final_chunks"]
        ]
        leetcode_chunks = [
            {
                **chunk,
                "context_role": "leetcode_candidate",
            }
            for chunk in leetcode_retrieval["final_chunks"]
        ]
        final_context = (
            "TECHNICAL EVIDENCE:\n"
            + technical_retrieval["context"]
            + "\n\n=== LEETCODE CANDIDATES ===\n\n"
            + leetcode_retrieval["context"]
        )

        return {
            "workflow": "related_problem",
            "source_restriction_origin": "related_problem_workflow",
            "selected_sources": list(
                dict.fromkeys(
                    technical_retrieval["selected_sources"]
                    + leetcode_retrieval["selected_sources"]
                )
            ),
            "technical_selected_sources": technical_retrieval[
                "selected_sources"
            ],
            "leetcode_selected_sources": leetcode_retrieval[
                "selected_sources"
            ],
            "explicit_source_restriction_detected": bool(explicit_sources),
            "technical_source_restriction_detected": bool(
                explicitly_selected_technical_sources
            ),
            "query_expansion": query_expansion,
            "technical_context": technical_retrieval["context"],
            "technical_chunks": technical_chunks,
            "pattern_extraction": pattern_extraction,
            "leetcode_search_query": leetcode_query,
            "leetcode_query_plan": leetcode_query_plan,
            # Retain the first query's expansion; all expansions are in retrieval_runs.
            "leetcode_query_expansion": retrieval_runs[0]["query_expansion"],
            "leetcode_retrieval_runs": retrieval_runs,
            "leetcode_candidates": [
                {"chunk_id": chunk_id, "source": doc.metadata["source"],
                 "page": doc.metadata["page"], "retrieved_by": candidate_queries[chunk_id]}
                for chunk_id, doc in candidate_docs.items()
            ],
            "leetcode_shortlist": shortlisted_chunks,
            "conceptual_judgments": conceptual_judgments,
            "relationship_extraction": relationship_extraction,
            "recommendation_validation": recommendation_validation,
            "leetcode_context": leetcode_retrieval["context"],
            "leetcode_chunks": leetcode_chunks,
            "final_context": final_context,
            "final_chunks": technical_chunks + leetcode_chunks,
            "generated_answer": response,
        }

    def run_turn(self, query, session):
        rewrite = self.rewrite_conversational_query(query, session)
        explicit_sources = find_explicit_sources(query, self.available_sources)

        if explicit_sources:
            session.active_sources = explicit_sources
            source_restriction_origin = "explicit_current_message"
        elif rewrite["is_follow_up"] and session.active_sources:
            source_restriction_origin = "inherited_from_previous_turn"
        else:
            session.active_sources = []
            source_restriction_origin = "none"

        standalone_query = rewrite["standalone_query"]
        result = self.run(
            standalone_query,
            source_override=session.active_sources or None,
        )

        # Conversation history helps resolve future references, but it is not added
        # to the retrieved document context or treated as source evidence.
        session.messages.append({"role": "user", "content": query})
        session.messages.append(
            {"role": "assistant", "content": result["generated_answer"]}
        )
        max_history_messages = self.config["conversation"]["max_history_turns"] * 2
        session.messages = session.messages[-max_history_messages:]

        result.update(
            {
                "original_query": query,
                "standalone_query": standalone_query,
                "conversation_rewrite": rewrite,
                "active_sources": list(session.active_sources),
                "source_restriction_origin": source_restriction_origin,
                "explicit_source_restriction_detected": bool(explicit_sources),
            }
        )
        return result


def main():
    with Path("config.yml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if config["indexing"]["mode"] == "build":
        pdf_paths = sorted(Path(".").glob(config["documents"]["pdf_glob"]))

        if not pdf_paths:
            raise FileNotFoundError("No PDF files were found in the current directory.")
    else:
        # Load mode reads the corpus, chunks, metadata, and indexes from disk.
        pdf_paths = []

    pipeline = RAGPipeline(config, pdf_paths)

    if config["conversation"]["enabled"]:
        session = ConversationSession()
        related_command = config["related_problem"]["command"].strip()
        exit_commands = {
            command.lower()
            for command in config["conversation"]["exit_commands"]
        }
        print("Conversation mode enabled. Type", ", ".join(sorted(exit_commands)), "to stop.")

        while True:
            try:
                current_query = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if current_query.lower() in exit_commands:
                break
            if not current_query:
                continue

            if current_query.casefold() == related_command.casefold():
                print(f"Provide a topic after {related_command}.")
                continue

            related_prefix = related_command.casefold() + " "
            if current_query.casefold().startswith(related_prefix):
                related_query = current_query[len(related_command):].strip()
                result = pipeline.run_related_problem(related_query)
                print(
                    "Technical evidence search sources:",
                    ", ".join(result["technical_selected_sources"]),
                )
                print("Reranked technical evidence:")
                for chunk in result["technical_chunks"]:
                    print(
                        f"  {chunk['rank']}. {chunk['source']}, "
                        f"PAGE: {chunk['page']}"
                    )
                print("Extracted source terms and inferred coding patterns:")
                print(json.dumps(result["pattern_extraction"], indent=2, ensure_ascii=False))
                print("LeetCode search query:", result["leetcode_search_query"])
                print("LeetCode task-query plan:")
                print(json.dumps(result["leetcode_query_plan"], indent=2, ensure_ascii=False))
                for index, retrieval in enumerate(result["leetcode_retrieval_runs"], start=1):
                    print(
                        f"  Query {index}: dense={len(retrieval['dense_chunk_ids'])}, "
                        f"BM25={len(retrieval['bm25_chunk_ids'])} candidates"
                    )
                print("Unique LeetCode candidates before reranking:", len(result["leetcode_candidates"]))
                print("Source-grounded relationship for matching:")
                print(json.dumps(result["relationship_extraction"], indent=2, ensure_ascii=False))
                print("Conceptual reranking judgments:")
                print(json.dumps(result["conceptual_judgments"], indent=2, ensure_ascii=False))
                print("Recommendation identity validation:")
                print(json.dumps(result["recommendation_validation"], indent=2, ensure_ascii=False))
                print(
                    "LeetCode candidate source:",
                    ", ".join(result["leetcode_selected_sources"]),
                )
                print("Reranked LeetCode problems:")
                for chunk in result["leetcode_chunks"]:
                    identity = chunk["problem_identity"]
                    print(
                        f"  {chunk['rank']}. {identity['number']}. {identity['title']} ({identity['difficulty']}), "
                        f"{chunk['source']}, "
                        f"PAGE: {chunk['page']}"
                    )
                print("\nAssistant:", result["generated_answer"])
                continue

            result = pipeline.run_turn(current_query, session)

            if result["source_restriction_origin"] == "inherited_from_previous_turn":
                print("Source restriction inherited:", ", ".join(result["active_sources"]))
            elif result["active_sources"]:
                print("Source explicitly selected:", ", ".join(result["active_sources"]))
            else:
                print("No source restriction; searching all sources.")

            if result["standalone_query"] != current_query:
                print("Standalone retrieval query:", result["standalone_query"])

            print("\nAssistant:", result["generated_answer"])
    else:
        query = config["query"]
        selected_sources = find_explicit_sources(query, pipeline.available_sources)

        if selected_sources:
            print("Source explicitly selected:", ", ".join(selected_sources))
        else:
            print("No source explicitly selected; searching all sources.")

        result = pipeline.run(query)
        print(result["generated_answer"])


if __name__ == "__main__":
    main()
