#########################################################################################################################################
# 1- Load the document
#########################################################################################################################################
import json
import os
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


class AzureOpenAILLM:
    """Keep the existing text-in/text-out calls while using Azure's v1 API."""

    def __init__(self, settings):
        from dotenv import load_dotenv
        from openai import OpenAI

        # Secrets stay in the environment or a git-ignored project .env file.
        load_dotenv(Path(__file__).with_name(".env"))
        azure = settings["azure"]
        api_key = os.environ.get(azure["api_key_env"], "").strip()
        if not api_key:
            raise ValueError(
                f"Set {azure['api_key_env']} in your environment or local .env file. "
                "Do not put the API key in config.yml."
            )
        self.client = OpenAI(
            base_url=azure["base_url"].rstrip("/") + "/",
            api_key=api_key,
            timeout=azure["timeout_seconds"],
            max_retries=azure["max_retries"],
        )
        self.settings = settings

    def invoke(self, prompt, pipeline_kwargs=None):
        # Reuse each stage's output limit; do not send local Transformers options.
        max_tokens = (pipeline_kwargs or {}).get(
            "max_new_tokens", self.settings["generation"]["max_new_tokens"]
        )
        messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt
        completion = self.client.chat.completions.create(
            model=self.settings["model_id"],  # Azure expects the deployment name.
            messages=messages,
            max_completion_tokens=max_tokens,
            reasoning_effort=self.settings["azure"]["reasoning_effort"],
            store=False,
        )
        content = completion.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(
                "Azure returned no answer text "
                f"(finish_reason={completion.choices[0].finish_reason})."
            )
        return content


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
    MODEL_TEXT_NORMALIZATION_VERSION = 1
    # Useful practice can cover only one component; closer connections rank first.
    RELATED_PRACTICE_LEVELS = ("direct_match", "related_practice", "stretch_connection")

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
            "text_normalization": {
                "enabled": self.config["text_normalization"]["enabled"],
                "version": self.MODEL_TEXT_NORMALIZATION_VERSION,
            },
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
                "Chunking, text normalization, embedding, BM25, or HNSW construction settings changed "
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
    def normalize_model_text(self, text):
        # Keep Documents and page_texts raw: normalization must not move citation
        # offsets, change chunk IDs, or break evaluation's original-PDF mappings.
        if not self.config["text_normalization"]["enabled"]:
            return text
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"(?<=\w)[-\u00ad\u2010\u2011][\t ]*\r?\n[\t ]*(?=\w)", "", text)
        return " ".join(text.split())

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
            self.normalize_model_text(text).lower()
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
                [self.normalize_model_text(chunk.page_content) for chunk in chunks]
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
        provider = self.config["llm"].get("provider", "local")
        if provider == "azure_openai":
            return AzureOpenAILLM(self.config["llm"])
        if provider != "local":
            raise ValueError('llm.provider must be either "local" or "azure_openai".')

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

    def format_chat_prompt(self, messages, **kwargs):
        # The API accepts messages directly; only local Qwen needs its tokenizer.
        if self.config["llm"].get("provider", "local") == "azure_openai":
            return messages
        return self.llm.pipeline.tokenizer.apply_chat_template(messages, **kwargs)

    def keep_conservative_terms(self, values, maximum):
        kept_terms = []
        seen_terms = set()

        if not isinstance(values, list):
            return kept_terms

        for value in values:
            if not isinstance(value, str):
                continue

            term = value.strip()
            normalized_term = self.normalize_model_text(term).casefold()

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
            query=self.normalize_model_text(query),
            max_key_terms=self.config["query_expansion"]["max_key_terms"],
            max_acronyms=self.config["query_expansion"]["max_acronyms"],
            min_variations=self.config["query_expansion"]["min_variations"],
            max_variations=self.config["query_expansion"]["max_variations"]
        )

        # Use Qwen's instruction/chat format, as in related-pattern extraction.
        expansion_prompt = self.format_chat_prompt(
            [{"role": "user", "content": expansion_prompt}],
            tokenize=False,
            add_generation_prompt=True,
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

        # Main terms must come from the question, not be invented adjacent topics.
        normalized_query = self.normalize_model_text(query).casefold()
        query_expansion["key_terms"] = [
            term for term in query_expansion["key_terms"]
            if re.search(
                r"(?<!\w)" + re.escape(self.normalize_model_text(term).casefold()) + r"(?!\w)",
                normalized_query,
            )
        ]
        retrieval_query = parsed_expansion.get("retrieval_query")
        primary_term = next(iter(query_expansion["key_terms"]), None)
        # Dropping a numerical condition changes the question. Filename numbers
        # are excluded because source filtering already uses the original query.
        query_without_sources = normalized_query
        for source in find_explicit_sources(query, getattr(self, "available_sources", [])):
            query_without_sources = query_without_sources.replace(
                self.normalize_model_text(source).casefold(), ""
            )
        number_pattern = r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
        query_numbers = set(re.findall(number_pattern, query_without_sources))
        if (
            self.config["query_expansion"]["use_focused_query"]
            and isinstance(retrieval_query, str)
            and 0 < len(retrieval_query.strip()) <= self.config["query_expansion"]["focused_query_max_length"]
            and retrieval_query.strip().endswith("?")
            and primary_term
            and set(re.findall(number_pattern, self.normalize_model_text(retrieval_query).casefold())) == query_numbers
            and re.search(
                r"(?<!\w)" + re.escape(self.normalize_model_text(primary_term).casefold()) + r"(?!\w)",
                self.normalize_model_text(retrieval_query).casefold(),
            )
        ):
            query_expansion["retrieval_query"] = retrieval_query.strip()
        else:
            query_expansion["retrieval_query"] = query

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

    def retrieve_candidates(self, query, expanded_query, source_override=None, retrieval_query=None):
        # Resolve source restrictions from the original question, never a rewrite
        # that may intentionally omit the filename.
        sources = self.selected_sources(query, source_override)

        # If a source was explicitly named, this searches only its chunks. Otherwise,
        # this searches all chunks from all sources.
        dense_results_with_scores = []
        if self.use_dense_retrieval:
            query_vector = self.embedding_model.embed_query(
                self.normalize_model_text(retrieval_query or query)
            )
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

        # A body chunk may omit its book title/heading. The existing source label
        # keeps domain context for ranking; it is not additional PDF evidence.
        pairs = [
            (
                self.normalize_model_text(query),
                (f"SOURCE: {doc.metadata['source']}\n" if self.config["reranking"]["include_source_name"] else "")
                + self.normalize_model_text(doc.page_content),
            )
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
                    page_content=self.normalize_model_text(doc.page_content)
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
        retrieval_query=None,
    ):
        retrieval = self.retrieve_candidates(
            query,
            expanded_query,
            source_override,
            retrieval_query=retrieval_query,
        )
        reranked_docs = self.rerank_candidates(
            retrieval_query or query,
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
            question=self.normalize_model_text(query)
        )

        # print(formatted_prompt)
        return formatted_prompt

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
        retrieval_query = query_expansion.get("retrieval_query", query)

        retrieval = self.retrieve_and_rerank_context(
            query,
            expanded_query,
            source_override,
            retrieval_query=retrieval_query,
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
            "retrieval_query": retrieval_query,
            "bm25_query": expanded_query,
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
            "coding_task_repairs": [],
        }
        if not technical_chunks:
            return fallback

        # Passage IDs are local to this extraction; Python owns their source/page mapping.
        passages = {f"P{index}": chunk for index, chunk in enumerate(technical_chunks, start=1)}
        technical_context = "\n\n".join(
            f"PASSAGE_ID: {passage_id}\nSOURCE: {chunk['source']}\nPAGE: {chunk['page']}\n{self.normalize_model_text(chunk['text'])}"
            for passage_id, chunk in passages.items()
        )
        base_prompt = settings["prompt"].format(
            question=self.normalize_model_text(query),
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
        task_repairs = {}
        feedback = ""
        # One corrective retry helps Qwen repair formatting or copying errors.
        for attempt in range(2):
            # Qwen-Instruct expects chat formatting for reliable instruction following.
            prompt = self.format_chat_prompt(
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
                                passage_text=self.normalize_model_text(passage["text"]),
                                quote_options=json.dumps(quote_options, ensure_ascii=False),
                                min_quote_words=settings["min_quote_words"],
                                max_quote_words=settings["max_quote_words"],
                            )
                            retry_prompt = self.format_chat_prompt(
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
                        # Keep the checked pattern/quote fixed; repair ONLY the task.
                        # The same source-linked pattern gets one focused call across retries.
                        repair_key = (passage_id, normalize(pattern["pattern"]), normalize(pattern["supporting_quote"]))
                        if repair_key not in task_repairs:
                            repair = {
                                "attempt": attempt + 1, "pattern": pattern["pattern"].strip(),
                                "passage_id": passage_id, "chunk_id": passage["chunk_id"],
                                "source": passage["source"], "page": passage["page"],
                                "original_coding_task": pattern["coding_task"].strip(),
                                "original_length": len(pattern["coding_task"].strip()),
                                "max_length": settings["max_query_length"],
                                "status": "failed", "coding_task": None, "error": None,
                            }
                            retry_prompt = settings["coding_task_retry_prompt"].format(
                                question=self.normalize_model_text(query),
                                pattern=json.dumps({field: pattern[field] for field in (
                                    "pattern", "reason", "topic_connection", "supporting_quote"
                                )}, ensure_ascii=False),
                                coding_task=repair["original_coding_task"],
                                passage_text=self.normalize_model_text(passage["text"]),
                                max_query_length=settings["max_query_length"],
                            )
                            retry_prompt = self.format_chat_prompt(
                                [{"role": "user", "content": retry_prompt}],
                                tokenize=False, add_generation_prompt=True,
                            )
                            repair["response"] = self.llm.invoke(
                                retry_prompt,
                                pipeline_kwargs={"max_new_tokens": settings["coding_task_retry_max_new_tokens"]},
                            )
                            try:
                                json_start = repair["response"].find("{")
                                if json_start == -1:
                                    raise ValueError("Coding-task retry returned no JSON object.")
                                result, _ = json.JSONDecoder().raw_decode(repair["response"][json_start:])
                                if not isinstance(result, dict) or set(result) != {"coding_task"}:
                                    raise ValueError("Return only a JSON object with coding_task.")
                                task = result["coding_task"]
                                if not isinstance(task, str) or not task.strip() or len(task.strip()) > settings["max_query_length"]:
                                    raise ValueError("Retried coding_task must be nonempty text within the configured character limit.")
                                repair.update(status="repaired", coding_task=task.strip(), repaired_length=len(task.strip()))
                            except (json.JSONDecodeError, ValueError) as retry_error:
                                repair["error"] = str(retry_error)
                            task_repairs[repair_key] = repair
                            fallback["coding_task_repairs"].append(repair)
                        repair = task_repairs[repair_key]
                        if repair["status"] != "repaired":
                            errors.append(f"Rejected coding_task {pattern['coding_task']!r}: exceeds {settings['max_query_length']} characters. Focused repair failed: {repair['error']}")
                            continue
                        # Python replaces this one field, never the pattern or its citations.
                        pattern = {**pattern, "coding_task": repair["coding_task"]}
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
            "coding_task_repairs": fallback["coding_task_repairs"],
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
        prompt = self.format_chat_prompt(
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

    def extract_related_relationship(self, pattern_extraction, technical_chunks, pattern_indices=None):
        patterns = pattern_extraction["transferable_patterns"]
        passages = {chunk["chunk_id"]: chunk for chunk in technical_chunks}

        def normalize(text):
            text = unicodedata.normalize("NFKC", text)
            text = re.sub(r"(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)", "", text)
            return " ".join(text.split())

        # Earlier relationship-extraction notes, retained for learning:
        # Keep the actual technical passage beside each pattern, not just its short quote.
        # Quote occurrence verifies provenance; conceptual relevance is still Qwen's judgment.
        # Read the original prose, not generated coding tasks or inferred mechanisms.
        # These passages already came from topic retrieval; the procedural question is not re-fed here.
        # Now Python anchors judging to the SAME accepted patterns used for search.
        # Pattern descriptions remain inferences; their original passages/quotes
        # remain the evidence. No new LLM-selected property can replace the target.
        outcome = {"status": "skipped_no_patterns", "method": "accepted_pattern_anchor",
                   "criteria": [], "rejected_patterns": [], "attempts": []}
        for index, pattern in enumerate(patterns, start=1):
            if pattern_indices is not None and index not in pattern_indices:
                continue
            passage = passages.get(pattern["chunk_id"])
            quote = normalize(pattern["supporting_quote"])
            if not passage or len(quote.split()) < 3 or quote not in normalize(passage["text"]):
                outcome["rejected_patterns"].append({"pattern_index": index, "error": "Pattern quote does not match its retrieved technical passage."})
                continue
            outcome["criteria"].append({
                "pattern_index": index,
                **{field: pattern[field] for field in ("pattern", "reason", "topic_connection", "coding_task")},
                "technical_quote": pattern["supporting_quote"],
                "technical_evidence": {key: passage[key] for key in ("chunk_id", "source", "page")},
            })
        if outcome["criteria"]:
            outcome["status"] = "extracted"
        elif patterns:
            outcome["status"] = "insufficient_evidence"
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
            footers = list(re.finditer(settings["footer_pattern"], text)) if error is None else []
            numbers = [int(match["number"]) for match in headers]
            first, last = (int(ranges[0]["first"]), int(ranges[0]["last"] or ranges[0]["first"])) if len(ranges) == 1 else (None, None)
            if error is None and (not headers or len(ranges) != 1 or len(set(numbers)) != len(numbers)
                                  or len(headers) != last - first + 1
                                  or min(numbers) != first or max(numbers) != last):
                error = "Problem headings are missing or ambiguous on this page."
            if error is None and (len(footers) != 1 or footers[0].start() < headers[-1].end()):
                error = "A unique statement-ending footer is unavailable; complete problem boundaries cannot be verified."
            if error:
                notes.append({"chunk_id": doc.metadata["chunk_id"], "source": source, "page": page,
                              "status": "unscored_problem_isolation", "note": error, "attempts": []})
                continue
            footer = footers[0]
            found_body = False
            for index, header in enumerate(headers):
                end = headers[index + 1].start() if index + 1 < len(headers) else footer.start()
                left, right = max(start, header.end()), min(start + len(doc.page_content), end)
                body = text[left:right] if left < right else ""
                if not body.strip():
                    continue
                left += len(body) - len(body.lstrip())
                right = left + len(body.strip())
                found_body = True
                problem_id = f"{source}::page={page}::problem={header['number']}"
                if problem_id not in groups:
                    full_body = text[header.end():end]
                    body_start = header.end() + len(full_body) - len(full_body.lstrip())
                    groups[problem_id] = {
                        "metadata": {**doc.metadata, "problem_id": problem_id,
                                     "problem_identity": {"number": int(header["number"]), "title": " ".join(header["title"].split()),
                                                          "difficulty": header["difficulty"], "heading_quote": header.group().strip()},
                                     "parent_chunk_ids": []},
                        "score": float(score), "spans": [],
                        "body_span": (body_start, body_start + len(full_body.strip())),
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
            # Retain that coverage as provenance. Explicitly fetch the whole identified
            # statement from saved source text, bounded by its heading and next heading/footer.
            page_text = self.page_texts[(metadata["source"], metadata["page"])]
            body_start, body_end = group["body_span"]
            body = page_text[body_start:body_end]
            metadata.update(start_index=body_start, problem_excerpts=[body],
                            problem_spans=[{"start": body_start, "end": body_end}],
                            retrieved_problem_spans=[{"start": left, "end": right} for left, right in spans],
                            problem_text_origin="saved_page_statement", problem_expanded=spans != [(body_start, body_end)])
            problem_docs.append((Document(page_content=body, metadata=metadata), group["score"]))
        return problem_docs, notes

    def related_evidence_spans(self, text, prefix, problem=False):
        # Select evidence by ID instead of asking Qwen to reproduce PDF spelling.
        # Offsets and quotes refer to the ORIGINAL supplied body, not normalized text.
        body = text
        if problem:
            constraints = re.search(r"(?im)^[\t ]*Constraints[.:]", body)
            if constraints:
                body = body[:constraints.start()]
        spans = {}
        for match in re.finditer(r'\S.*?(?:[.!?](?=\s+[A-Z"\u201c]|\s*$)|\Z)', body, re.DOTALL):
            quote = match.group().rstrip()
            if len(quote.split()) >= 3:
                identifier = f"{prefix}{len(spans) + 1}"
                spans[identifier] = {"id": identifier, "start": match.start(),
                                     "end": match.start() + len(quote), "quote": quote}
        return spans

    def select_related_evidence(self, identifier, spans):
        if not isinstance(identifier, str) or identifier not in spans:
            raise ValueError(f"Select one existing evidence span ID from {list(spans)}, or use null with unrelated.")
        return spans[identifier]

    def rerank_related_candidates(self, query, pattern_extraction, technical_chunks, shortlisted_docs, pattern_indices=None, retrieval_query=None):
        settings = self.config["related_problem"]["conceptual_reranking"]
        problem_docs, isolation_notes = self.isolate_related_problems(shortlisted_docs)
        relationship = self.extract_related_relationship(pattern_extraction, technical_chunks, pattern_indices) if problem_docs else {
            "status": "skipped_no_candidates", "attempts": [],
        }
        passages = {chunk["chunk_id"]: chunk for chunk in technical_chunks}
        criteria = {criterion["pattern_index"]: criterion for criterion in relationship.get("criteria", [])}
        judgments, accepted = isolation_notes, []

        def normalize(text):
            text = unicodedata.normalize("NFKC", text)
            text = re.sub(r"(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)", "", text)
            return " ".join(text.split())

        # No numeric rating: a chunk either supports this specific relationship or does not.
        # Each candidate is now ONE problem's retrieved prose, not an entire mixed-problem chunk.
        # Keep the binary match_label for existing diagnostics, but ask Qwen for
        # a practice level instead of requiring the whole mechanism to match.
        levels = self.RELATED_PRACTICE_LEVELS + ("unrelated",)
        max_operations = settings["max_problem_operations"]
        if type(max_operations) is not int or max_operations < 1:
            raise ValueError("related_problem.conceptual_reranking.max_problem_operations must be a positive integer.")
        technical_spans_by_pattern = {
            index: self.related_evidence_spans(passages[criterion["technical_evidence"]["chunk_id"]]["text"], f"T{index}.")
            for index, criterion in criteria.items()
        }
        technical_patterns = [
            {
                **{field: criterion[field] for field in ("pattern_index", "pattern", "reason", "topic_connection")},
                "text": self.normalize_model_text(passages[criterion["technical_evidence"]["chunk_id"]]["text"]),
                "spans": {key: normalize(span["quote"]) for key, span in technical_spans_by_pattern[index].items()},
            }
            for index, criterion in criteria.items()
        ]
        for rank, (doc, cross_encoder_score) in enumerate(problem_docs, start=1):
            problem_spans = self.related_evidence_spans(doc.page_content, "P", problem=True)
            judgment = {
                "chunk_id": doc.metadata["chunk_id"], "source": doc.metadata["source"],
                "page": doc.metadata["page"], "shortlist_rank": rank,
                "cross_encoder_score": float(cross_encoder_score), "attempts": [],
                "problem_id": doc.metadata["problem_id"], "problem_identity": doc.metadata["problem_identity"],
                "parent_chunk_ids": doc.metadata["parent_chunk_ids"], "problem_text": doc.page_content,
                "problem_evidence_spans": list(problem_spans.values()),
                "problem_expansion": {key: doc.metadata[key] for key in (
                    "problem_text_origin", "problem_expanded", "problem_spans", "retrieved_problem_spans"
                )},
            }
            if relationship["status"] != "extracted":
                judgments.append({**judgment, "status": "skipped_no_relationship",
                                  "note": "No usable technical relationship; no conceptual recommendation is supported."})
                continue
            if not problem_spans:
                judgments.append({**judgment, "status": "rejected",
                                  "note": "No selectable problem prose; constraints alone do not establish an operation."})
                continue
            base_prompt = settings["prompt"].format(
                # The candidate judge quotes ONLY problem text. The independent
                # verifier below receives the technical quote and original prose.
                # Now Python copies the selected span; Qwen supplies no quote text.
                # First extract operations BLIND to the question, pattern, and ranking.
                candidate_text=self.normalize_model_text(doc.page_content),
                problem_spans=json.dumps({key: normalize(span["quote"]) for key, span in problem_spans.items()}, ensure_ascii=False),
                max_operations=max_operations,
            )
            feedback = ""
            # One call per candidate, with one bounded corrective retry if invalid.
            for attempt in range(2):
                prompt = self.format_chat_prompt(
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
                    if not isinstance(result, dict) or not isinstance(result.get("operations"), list):
                        raise ValueError("Return an operations list; no topic or relationship judgment belongs in this pass.")
                    if len(result["operations"]) > max_operations:
                        raise ValueError(f"Extract at most {max_operations} atomic operations.")
                    operations = []
                    for item in result["operations"]:
                        if not isinstance(item, dict) or not isinstance(item.get("operation"), str) or not item["operation"].strip():
                            raise ValueError("Each operation needs a nonempty description.")
                        span = self.select_related_evidence(item.get("problem_span_id"), problem_spans)
                        # Python owns the chunk IDs and citations, never generated IDs/pages.
                        operations.append({"operation_id": f"O{len(operations) + 1}",
                                           "operation": item["operation"].strip(), "problem_evidence_span": span})
                    judgment["attempts"].append({"attempt": attempt + 1, "response": response, "error": None})
                    judgment.update(problem_operations=operations, extraction_status="valid", status="rejected")
                    if not operations:
                        judgment.update(match_label="unrelated", connection_level="unrelated",
                                        note="No explicit coding operation was extracted; no connection was forced.")
                    break
                except (json.JSONDecodeError, ValueError) as error:
                    judgment["attempts"].append({"attempt": attempt + 1, "response": response, "error": str(error)})
                    judgment.update(status="unscored", extraction_status="unscored")
                    feedback = "\nCORRECTION: " + str(error) + " Return only atomic operations and their supplied P span IDs. Do not invent a task or assess relationships; return an empty operations list if none is explicit."

            if judgment.get("problem_operations"):
                # A separate call checks the claim against BOTH original passages.
                # It does not see the candidate judge's label, explanation, or numeric score.
                # Compare one FIXED technical pattern with one frozen, blind-extracted
                # operation. This pass cannot rewrite a problem operation to fit the topic.
                operations_by_id = {op["operation_id"]: op for op in judgment["problem_operations"]}
                base_prompt = settings["verification_prompt"].format(
                    technical_patterns=json.dumps(technical_patterns, ensure_ascii=False),
                    problem_operations=json.dumps([
                        {"operation_id": op["operation_id"], "operation": op["operation"],
                         "problem_span_id": op["problem_evidence_span"]["id"],
                         "evidence": normalize(op["problem_evidence_span"]["quote"])}
                        for op in judgment["problem_operations"]
                    ], ensure_ascii=False),
                    question=self.normalize_model_text(query),
                )
                verification = {"status": "unscored", "attempts": []}
                feedback = ""
                for attempt in range(2):
                    prompt = self.format_chat_prompt(
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
                        if not isinstance(result, dict) or result.get("connection_level") not in levels:
                            raise ValueError(f"connection_level must be one of {levels}.")
                        for field in ("technical_operation_grounded", "problem_operation_grounded", "component_supported"):
                            if type(result.get(field)) is not bool:
                                raise ValueError(f"Provide a JSON boolean for {field}.")
                        # Ground each operation in ITS OWN source, independently of similarity.
                        # Different grounded operations can still share a useful component.
                        operations_supported = (result["technical_operation_grounded"]
                                                and result["problem_operation_grounded"])
                        supported = (result["connection_level"] in self.RELATED_PRACTICE_LEVELS
                                     and operations_supported and result["component_supported"])
                        if supported:
                            index = result.get("pattern_index")
                            if type(index) is not int or index not in criteria:
                                raise ValueError(f"Select one existing pattern_index from {list(criteria)}.")
                            operation_id = result.get("problem_operation_id")
                            if not isinstance(operation_id, str) or operation_id not in operations_by_id:
                                raise ValueError(f"Select one existing problem_operation_id from {list(operations_by_id)}; do not rewrite operations.")
                            for field in ("technical_component", "problem_component", "shared_component", "important_difference"):
                                if not isinstance(result.get(field), str) or not result[field].strip():
                                    raise ValueError(f"For useful practice, provide a nonempty {field}.")
                            criterion = criteria[index]
                            operation = operations_by_id[operation_id]
                            technical_spans = technical_spans_by_pattern[index]
                            technical_span = self.select_related_evidence(result.get("technical_span_id"), technical_spans)
                            problem_span = operation["problem_evidence_span"]
                            judgment.update(pattern_index=index, problem_operation_id=operation_id,
                                            technical_operation=criterion["pattern"], problem_operation=operation["operation"],
                                            candidate_relationship=operation["operation"], shared_mechanism=criterion["pattern"],
                                            technical_relationship=criterion["pattern"], technical_evidence=criterion["technical_evidence"],
                                            technical_evidence_spans=list(technical_spans.values()),
                                            proposed_leetcode_quote=problem_span["quote"],
                                            anchored_technical_quote=criterion["technical_quote"],
                                            technical_quote=technical_span["quote"], leetcode_quote=problem_span["quote"],
                                            technical_evidence_span=technical_span, problem_evidence_span=problem_span,
                                            important_difference=result["important_difference"].strip())
                        final_level = result["connection_level"] if supported else "unrelated"
                        # Side descriptions also stay bound to the selected records.
                        # A free-text bridge proposal cannot rename the coding operation.
                        technical_component = judgment.get("technical_operation") if supported else result.get("technical_component")
                        problem_component = judgment.get("problem_operation") if supported else result.get("problem_component")
                        explanation = (
                            f"Technical component: {technical_component or 'none supported'}. "
                            f"Problem component: {problem_component or 'none supported'}. "
                            f"Shared component: {result.get('shared_component') or 'none supported'}."
                        )
                        verification.update(status="valid", supported=supported, connection_level=final_level,
                                            reported_connection_level=result["connection_level"], explanation=explanation,
                                            **{field: result[field] for field in ("technical_operation_grounded", "problem_operation_grounded",
                                                                               "component_supported")})
                        verification.update(technical_operation=judgment.get("technical_operation"),
                                            problem_operation=judgment.get("problem_operation"),
                                            technical_component=technical_component or "",
                                            problem_component=problem_component or "",
                                            proposed_technical_component=result.get("technical_component", ""),
                                            proposed_problem_component=result.get("problem_component", ""))
                        # Derived compatibility field for the existing diagnostic readers.
                        verification["operations_supported"] = operations_supported
                        verification["shared_component"] = result.get("shared_component", "")
                        judgment.update(explanation=explanation, shared_component=result.get("shared_component", ""))
                        verification["attempts"].append({"attempt": attempt + 1, "response": response, "error": None})
                        # The independent source check owns the final practice level.
                        judgment["proposed_connection_level"] = result["connection_level"]
                        judgment["connection_level"] = final_level
                        judgment["match_label"] = "supported_match" if supported else "unrelated"
                        judgment["status"] = "accepted" if supported else "rejected"
                        if supported:
                            doc.metadata["connection_level"] = final_level
                            accepted.append((doc, cross_encoder_score))
                        break
                    except (json.JSONDecodeError, ValueError) as error:
                        verification["attempts"].append({"attempt": attempt + 1, "response": response, "error": str(error)})
                        judgment["status"] = "unscored"
                        feedback = "\nCORRECTION: " + str(error) + " Select only supplied pattern/operation/span IDs. The frozen operation and its evidence cannot change. Return unrelated if either side lacks evidence for the proposed bridge."
                judgment["verification"] = verification
            judgments.append(judgment)

        # Previously, ordinal ratings ranked links:
        # Stronger conceptual links first; the cross-encoder breaks ties.
        # Now every retained link passed both checks; keep cross-encoder order within that set.
        # Score complete accepted problems against the same coding-search queries.
        # Retain inherited chunk scores as provenance; fixed-input judge controls
        # omit retrieval_query and continue bypassing cross-encoder selection.
        problem_scores = {}
        if retrieval_query is not None:
            for doc, score in accepted:
                doc.metadata["chunk_cross_encoder_score"] = float(score)
            accepted = self.rerank_candidates(
                retrieval_query, [doc for doc, _ in accepted], top_k=len(accepted),
            )
            for doc, score in accepted:
                doc.metadata["problem_cross_encoder_score"] = float(score)
                problem_scores[doc.metadata["problem_id"]] = float(score)
        # Prefer direct/related practice before stretch suggestions, then use the
        # existing cross-encoder score within each level. No retrieval changes.
        accepted.sort(key=lambda item: (self.RELATED_PRACTICE_LEVELS.index(item[0].metadata["connection_level"]), -float(item[1])))
        selected = accepted[:self.config["reranking"]["final_top_k"]]
        selected_ids = {doc.metadata["problem_id"] for doc, _ in selected}
        for judgment in judgments:
            if retrieval_query is not None:
                judgment["problem_cross_encoder_score"] = problem_scores.get(judgment.get("problem_id"))
            judgment["selected_for_context"] = judgment.get("problem_id") in selected_ids
        return selected, judgments, relationship

    def generate_related_recommendations(self, selected_judgments):
        settings = self.config["related_problem"]["recommendation_validation"]
        if type(settings["max_recommendations"]) is not int or settings["max_recommendations"] < 1:
            raise ValueError("related_problem.recommendation_validation.max_recommendations must be a positive integer.")
        accepted, attempts, rejected = {}, [], []
        # Earlier final-model selection notes, retained for learning:
        # The LLM may propose identities; only exact source-verified identities can be displayed.
        # Python renders titles, difficulty, and citations from the selected source records.
        # A bare JSON array is harmless; every proposed identity still gets the same strict checks.
        # Now Python takes the already-ranked approved records directly: no final
        # LLM selection, generated identities, JSON parsing, or corrective retry.
        # Quote and source-heading validation remain in the upstream judges/isolator.
        for judgment in selected_judgments:
            if (judgment.get("status") != "accepted" or judgment.get("match_label") != "supported_match"
                    or judgment.get("connection_level") not in self.RELATED_PRACTICE_LEVELS
                    or judgment.get("verification", {}).get("status") != "valid"
                    or judgment.get("verification", {}).get("supported") is not True
                    or judgment["verification"].get("connection_level") != judgment["connection_level"]
                    or not judgment.get("selected_for_context")):
                rejected.append({"problem_id": judgment.get("problem_id"), "error": "Candidate must pass both relevance checks and belong to final context."})
                continue
            accepted.setdefault(judgment["problem_id"], judgment)
            if len(accepted) >= settings["max_recommendations"]:
                break

        blocks = []
        for judgment in accepted.values():
            identity, technical = judgment["problem_identity"], judgment["technical_evidence"]
            blocks.append(
                f"{identity['number']}. {identity['title']} ({identity['difficulty']})\n"
                f"Connection: {judgment['connection_level'].replace('_', ' ').capitalize()}\n"
                f"Related practice pattern: {judgment['shared_mechanism']}\n"
                f"What transfers: {judgment['verification']['explanation']}\n"
                f"Important difference: {judgment['important_difference']}\n"
                f"Technical quote: {judgment['technical_quote']}\n"
                f"Problem quote: {judgment['leetcode_quote']}\n"
                f"SOURCES: {technical['source']}, PAGE: {technical['page']}; {judgment['source']}, PAGE: {judgment['page']}"
            )
        response = "\n\n".join(blocks) if blocks else "No source-verified recommendation was selected; no problem details have been guessed."
        return response, {"status": "validated" if blocks else "no_valid_recommendations", "method": "deterministic_ranked_selection", "attempts": attempts,
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
        retrieval_query = query_expansion.get("retrieval_query", query)

        # Technical evidence is retrieved independently from the LeetCode
        # candidates so that each stage remains visible and testable.
        technical_retrieval = self.retrieve_and_rerank_context(
            query,
            expanded_query,
            source_override=technical_sources,
            retrieval_query=retrieval_query,
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
        searched_pattern_indices = [
            index for index, pattern in enumerate(pattern_extraction["transferable_patterns"], start=1)
            if any(search["pattern_index"] == index or (
                search["pattern_index"] is None and pattern["coding_task"] in search["query"]
            ) for search in leetcode_query_plan["queries"])
        ]
        shortlisted_docs = self.rerank_candidates(
            leetcode_query, list(candidate_docs.values()),
            top_k=shortlist_top_k,
        )
        _, shortlisted_chunks = self.build_context(shortlisted_docs)
        conceptually_ranked_docs, conceptual_judgments, relationship_extraction = self.rerank_related_candidates(
            query, pattern_extraction, technical_retrieval["final_chunks"], shortlisted_docs,
            pattern_indices=searched_pattern_indices, retrieval_query=leetcode_query,
        )
        context, final_chunks = self.build_context(conceptually_ranked_docs)
        for chunk, (doc, _) in zip(final_chunks, conceptually_ranked_docs):
            chunk.update({key: doc.metadata[key] for key in (
                "problem_id", "problem_identity", "parent_chunk_ids", "problem_spans", "problem_excerpts",
                "retrieved_problem_spans", "problem_text_origin", "problem_expanded",
                "chunk_cross_encoder_score", "problem_cross_encoder_score", "connection_level"
            )})
        leetcode_retrieval = {
            "selected_sources": [leetcode_source], "context": context, "final_chunks": final_chunks,
        }

        selected_by_id = {judgment["problem_id"]: judgment for judgment in conceptual_judgments if judgment["selected_for_context"]}
        selected_judgments = [
            selected_by_id[doc.metadata["problem_id"]] for doc, _ in conceptually_ranked_docs
        ]
        # Do not ask the answer model to fill in a recommendation after the gate rejects everything.
        if final_chunks:
            response, recommendation_validation = self.generate_related_recommendations(selected_judgments)
        else:
            response = (
                "No related LeetCode recommendation is supported by the current retrieved evidence: "
                "no candidate passed conceptual reranking. See the extraction and judgment diagnostics."
            )
            recommendation_validation = {"status": "skipped_no_candidates", "method": "deterministic_ranked_selection", "attempts": [], "rejected_items": [], "accepted_problem_ids": []}

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
            "technical_retrieval_query": retrieval_query,
            "technical_context": technical_retrieval["context"],
            "technical_chunks": technical_chunks,
            "pattern_extraction": pattern_extraction,
            "leetcode_search_query": leetcode_query,
            "leetcode_query_plan": leetcode_query_plan,
            "searched_pattern_indices": searched_pattern_indices,
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
            if result["retrieval_query"] != result["standalone_query"]:
                print("Focused dense/reranking query:", result["retrieval_query"])

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
