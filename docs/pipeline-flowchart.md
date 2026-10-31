# Pipeline flowchart — draft

Current default workflows. Purple boxes are **Azure OpenAI API calls using GPT-5.1**. Blue boxes run locally. Dashed arrows show reused data, retries, or the next chat turn.

```mermaid
flowchart TD
    subgraph SOURCES["Indexing & source preparation"]
        PDF["PDF library"]
        INGEST["Extract prose & create overlapping chunks<br/>pypdf · LangChain"]
        BUILD["Embed normalized chunks & build indexes<br/>MiniLM · FAISS Flat + HNSW · BM25"]
        STORE[("Persisted corpus & indexes<br/>index-data/")]
        CATALOGUE[("LeetCode catalogue<br/>4,000 problem identities & statements")]

        PDF -->|Build mode| INGEST --> BUILD --> STORE
        PDF -->|Parse original LeetCode PDF| CATALOGUE
    end

    USER["User question"]
    REWRITE["Resolve follow-ups from QA history<br/>GPT-5.1 API · later QA turns only"]
    SCOPE["Apply source restrictions<br/>Exact filename, inherited scope, or all allowed sources"]

    USER -->|Document QA| REWRITE
    USER -->|/related · independent of history| SCOPE
    REWRITE --> SCOPE

    subgraph QA["Shared document-QA pipeline"]
        EXPAND["Focus query & expand keywords<br/>GPT-5.1 API"]
        DENSE["Dense retrieval<br/>MiniLM · Flat kNN or HNSW ANN"]
        BM25["Sparse retrieval<br/>BM25 keyword matching"]
        MERGE["Merge & deduplicate candidates"]
        RERANK["Cross-encoder reranking<br/>MiniLM · keep top 4 chunks"]
        CONTEXT["Assemble context<br/>Source filenames & physical PDF pages"]
        ANSWER["Generate grounded answer<br/>GPT-5.1 API"]

        EXPAND -->|Focused query| DENSE
        EXPAND -->|Original query + expanded terms| BM25
        DENSE --> MERGE
        BM25 --> MERGE
        MERGE --> RERANK --> CONTEXT --> ANSWER
    end

    SCOPE --> EXPAND
    STORE -.->|Load / reuse| DENSE
    STORE -.->|Load / reuse| BM25
    ANSWER --> REQUEST{"LeetCode practice requested?"}
    REQUEST -->|No| OUTPUT["Display cited answer"]

    subgraph PRACTICE["LeetCode recommendations · title selection"]
        TITLES["Shortlist up to 20 problems from all titles<br/>GPT-5.1 API"]
        VERIFY["Compare shortlisted full statements with technical evidence<br/>GPT-5.1 API · select up to 3 & explain connections"]
        CHECK["Python: validate problem identities & evidence span IDs<br/>Render cited recommendations, or abstain"]

        TITLES --> VERIFY --> CHECK
        TITLES -.->|Invalid JSON / IDs: retry once| TITLES
        CHECK -.->|Invalid JSON / spans: retry once| VERIFY
    end

    REQUEST -->|Yes · grounded answer + evidence| TITLES
    CATALOGUE -.->|All numbers & titles| TITLES
    CATALOGUE -.->|Only shortlisted statements| VERIFY
    CONTEXT -.->|Original technical evidence| VERIFY
    CHECK --> RELATED_OUTPUT["Display grounded answer + recommendations"]
    OUTPUT -.->|Save QA history · next message| USER
    RELATED_OUTPUT -.->|Next message · QA history unchanged| USER

    classDef api fill:#EDE9FE,stroke:#7C3AED,color:#3B0764,stroke-width:2px
    classDef local fill:#E0F2FE,stroke:#0284C7,color:#0C4A6E
    classDef data fill:#F1F5F9,stroke:#64748B,color:#0F172A
    classDef result fill:#DCFCE7,stroke:#16A34A,color:#14532D
    classDef decision fill:#FEF3C7,stroke:#D97706,color:#78350F
    class REWRITE,EXPAND,ANSWER,TITLES,VERIFY api
    class INGEST,BUILD,SCOPE,DENSE,BM25,MERGE,RERANK,CONTEXT,CHECK local
    class PDF,STORE,CATALOGUE data
    class USER,OUTPUT,RELATED_OUTPUT result
    class REQUEST decision
```

- **Build once, load later:** build mode persists both FAISS indexes and BM25. Load mode reuses the saved corpus and selected dense index. The LeetCode catalogue is parsed from the original PDF and cached in memory separately.
- **Source grounding:** `/related` retrieves technical evidence outside the LeetCode PDF. GPT-5.1 judges conceptual relationships. Python validates identities and citation spans, then formats the recommendations without another LLM call. Empty technical evidence or an empty shortlist skips the remaining selection calls.
- **Loops and settings:** chat continues until `exit` or `quit`. Each title-selection stage allows one corrective retry by default, then reports failure if still invalid. API rate-limit retries are omitted from the diagram. Retrieval toggles and numerical limits come from `config.yml`.
