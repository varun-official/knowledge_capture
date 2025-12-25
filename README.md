# Knowledge Capture API

High-end RAG API using MongoDB, Voyage AI, and Gemini.

## Setup
1. `uv sync`
2. `cp .env.example .env` (Add Keys)

## MongoDB Indexes (Critical)
Run this in Atlas Search:

**Vector Index (`vector_index`)**
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

**Text Index (`text_index`)**
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

## Running
*   **API**: `uv run uvicorn src.server:app --reload`
*   **Worker**: `uv run worker.py`
