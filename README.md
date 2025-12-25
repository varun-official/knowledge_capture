# Knowledge Capture API

State-of-the-art RAG (Retrieval Augmented Generation) API built for **High-End Use Cases**.
It features **Multi-Tenancy**, **Advanced Ingestion**, and **Dynamic Retrieval Strategies**.

---

## 🏛️ Architecture

### Tech Stack
*   **Framework**: FastAPI + Uvicorn
*   **Database**: MongoDB Atlas (Beanie ODM + GridFS)
*   **Ingestion**: Docling (PDF Parsing) + Voyage AI (`voyage-3` embeddings)
*   **Retrieval**: MongoDB Atlas Search + Voyage AI
*   **LLM**: Gemini Pro (via LiteLLM)

### Multi-Tenancy (Isolation)
All data is strictly isolated by `user_email`.
*   **Files**: Tagged with `user_corpus=user_email`.
*   **Chunks**: Tagged with `user_corpus=user_email`.
*   **Search**: Every retrieval query applies a strict filter: `{"user_corpus": {"$eq": user_email}}`.

---

## 🚀 Features

### 1. Advanced Ingestion
*   **PDF Parsing**: Uses **Docling** to accurately parse text, tables, and headers.
*   **Hybrid Chunking**: Respects document hierarchy (headers) using `HybridChunker` + `Contextualizer`.
*   **Embeddings**: Uses **Voyage-3** (1024 d) for SOTA semantic understanding.

### 2. Dynamic Retrieval Strategies
The API supports 7 different strategies to handle various query complexities.

| Strategy | Description | Best For |
| :--- | :--- | :--- |
| `vector` (Default) | Semantic search using cosine similarity. | Standard questions. |
| `keyword` | Full-text search (BM25) using Lucene. | Exact phrase matching. |
| `hybrid` | Combines Vector + Keyword with **RRF Fusion**. | Best general purpose. |
| `multi_query_vector` | Generates 3 variations -> Parallel Vector Searches -> RRF. | Ambiguous questions. |
| `multi_query_hybrid` | Generates 3 variations -> Parallel Hybrid Searches -> RRF. | Max recall. |
| `query_decompose_vector` | Breaks complex query into sub-questions -> Parallel Vector -> RRF. | Multi-part questions. |
| `query_decompose_hybrid` | Breaks complex query into sub-questions -> Parallel Hybrid -> RRF. | Complex research. |

---

## 🛠️ Setup

### Prerequisites
*   Python 3.12+
*   `uv` (Package Manager)
*   MongoDB Atlas Account
*   Voyage AI API Key
*   Gemini API Key

### Installation
1.  **Install Dependencies**:
    ```bash
    uv sync
    ```
2.  **Environment Variables**:
    ```bash
    cp .env.example .env
    # Fill in MONGODB_URI, VOYAGE_API_KEY, GEMINI_API_KEY
    ```

### MongoDB Indexes (CRITICAL)
You **MUST** create these indexes in MongoDB Atlas Search for the system to work.

**1. Vector Index (`vector_index`)**
```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1024,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "user_corpus"
    }
  ]
}
```

**2. Text Index (`text_index`)**
```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "content": {
        "type": "string",
        "analyzer": "lucene.standard"
      },
      "user_corpus": {
        "type": "string",
        "analyzer": "lucene.keyword"
      }
    }
  }
}
```

---

## 🔌 API Usage

### 1. Upload File
Ingests a file into the user's corpus.

`POST /files/upload`
*   `file`: (Binary)
*   `user_email`: "alice@example.com"

### 2. Chat / Query
Asks a question to the user's knowledge base.

`POST /chat/query`
```json
{
  "query": "What is the revenue growth?",
  "user_email": "alice@example.com",
  "rag_strategy": "multi_query_hybrid" 
}
```
*   **`rag_strategy` Options**: `vector`, `keyword`, `hybrid`, `multi_query_vector`, `multi_query_hybrid`, `query_decompose_vector`, `query_decompose_hybrid`.

### Response Format
```json
{
  "answer": "The revenue grew by 20%...",
  "sources": [
    {
      "content": "Revenue report...",
      "score": 0.89,
      "document_id": "676b...",
      "metadata": { "source": "Q3_Report.pdf" }
    }
  ]
}
```

---

## 🏃 Running locally

**Start API**:
```bash
uv run src/server.py
```

**Start Worker** (In separate terminal):
```bash
uv run worker.py
```
