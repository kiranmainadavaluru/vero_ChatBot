# RAG Chatbot - Complete Flow Explanation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [System Architecture](#system-architecture)
4. [Complete Application Flow](#complete-application-flow)
5. [Detailed Module Breakdown](#detailed-module-breakdown)
6. [Data Flow Diagrams](#data-flow-diagrams)

---

## Project Overview

The **RAG Chatbot** (Retrieval-Augmented Generation Chatbot) is an intelligent document question-answering system that allows users to upload various document types, index them, and ask questions about their content. The system uses vector embeddings and semantic search to find relevant document chunks and generates answers using a large language model.

**Key Features:**
- Support for multiple document formats (PDF, DOCX, XLSX, CSV, TXT, PPTX, HTML, JSON, XML)
- Vector-based semantic search for finding relevant document chunks
- Intelligent document routing (prevents mixing content from different documents)
- Multi-session chat history persistence
- Visual evidence display with relevance scores
- Real-time document management

---

## Technology Stack

### Backend
- **Framework:** Flask (Python web framework)
- **Vector Database:** Weaviate (semantic search and vector storage)
- **SQL Database:** PostgreSQL (chat history)
- **Embedding Model:** Sentence Transformers (`all-MiniLM-L6-v2`)
- **LLM:** Hugging Face Inference API (`moonshotai/Kimi-K2-Instruct-0905`)
- **Document Processing:** 
  - PyPDF2 (PDF)
  - python-docx (DOCX)
  - openpyxl (Excel)
  - python-pptx (PowerPoint)
  - BeautifulSoup (HTML)
  - Custom JSON/XML parsers

### Frontend
- **Framework:** React with Vite
- **Styling:** CSS
- **API Communication:** Fetch API

### Infrastructure
- **Containerization:** Docker Compose
- **Services:** Backend, Frontend, Weaviate, PostgreSQL

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface (React)                   │
│              - Chat interface                                │
│              - File upload                                   │
│              - Document management                           │
│              - Session history                               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ HTTP/REST API
                 │
┌────────────────▼────────────────────────────────────────────┐
│                  Flask Backend (app.py)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Upload     │  │   Ask/Chat   │  │ Document/Session│   │
│  │   Service    │  │   Routes     │  │  Management     │   │
│  └────────┬─────┘  └──────┬───────┘  └────────┬────────┘   │
└───────────┼────────────────┼───────────────────┼────────────┘
            │                │                   │
    ┌───────▼────────┐   ┌───▼────────────┐   ┌─▼──────────┐
    │ Document       │   │ Retrieval      │   │ PostgreSQL │
    │ Processing     │   │ Service        │   │ Database   │
    │ - Loaders      │   │ - Vector       │   │            │
    │ - Chunking     │   │   search       │   │ Sessions & │
    │ - Embedding    │   │ - Document     │   │ Messages   │
    │                │   │   routing      │   │            │
    └────────┬───────┘   └───┬────────────┘   └────────────┘
             │               │
             │       ┌───────▼──────────┐
             └──────►│  Weaviate        │
                     │  Vector Store    │
                     │                  │
                     │ - Embeddings     │
                     │ - Chunks         │
                     │ - Metadata       │
                     └──────────────────┘
```

---

## Complete Application Flow

### Phase 1: Application Startup

```
1. Docker Containers Start
   ├── PostgreSQL (port 5432) - Database initialization
   ├── Weaviate (port 8080) - Vector database initialization
   └── Flask Backend (port 5000) - Application server

2. Backend Initialization (app.py)
   ├── Load configuration from config.py
   ├── Initialize Weaviate client
   │   ├── Connect to http://localhost:8080
   │   └── Create "DocumentChunk" schema if not exists
   ├── Initialize PostgreSQL connection pool
   │   └── Create chat_sessions and chat_messages tables
   ├── Load embedding model (Sentence Transformers)
   └── Load Hugging Face LLM client
   
3. Frontend Loads (React + Vite)
   ├── Fetch /api/health to check backend status
   ├── Load previous sessions from /api/sessions
   ├── Load document list from /api/documents
   └── Display chat interface

✅ System Ready for User Interaction
```

---

### Phase 2: Document Upload Flow

**User Action:** User selects and uploads a document file

```
┌─ FRONTEND (App.jsx) ─────────────────────────────────────┐
│                                                           │
│ 1. User clicks "Upload File" button                       │
│ 2. File picker opens (HTML input)                         │
│ 3. User selects file (e.g., "report.pdf")                 │
│ 4. File sent via POST /api/upload                         │
│    └─ FormData with file in "files" field                 │
│                                                           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─ BACKEND (app.py - upload endpoint) ──────────────────────┐
│                                                            │
│ 1. Receive file upload                                     │
│ 2. Call upload_service.ingest_upload(file)                │
│                                                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌─ UPLOAD SERVICE (upload_service.py) ──────────────────────┐
│                                                            │
│ 1. Validate file extension                                │
│    └─ Check against ALLOWED_EXTENSIONS in config.py       │
│                                                            │
│ 2. Sanitize filename using secure_filename()              │
│                                                            │
│ 3. Generate unique path                                   │
│    └─ If filename exists: append " (1)", " (2)", etc.    │
│                                                            │
│ 4. Save file to documents/ directory                      │
│                                                            │
│ 5. Call ingest_saved_file() for processing                │
│                                                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌─ DOCUMENT LOADER (document_loaders.py) ────────────────────┐
│                                                            │
│ Dispatcher Pattern:                                        │
│ ├─ Detect file extension (.pdf, .docx, .xlsx, etc.)      │
│ └─ Route to appropriate loader:                           │
│    ├─ pdf_loader.load_pdf()                              │
│    ├─ docx_loader.load_docx()                            │
│    ├─ excel_loader.load_excel()                          │
│    ├─ csv_loader.load_csv()                              │
│    ├─ txt_loader.load_txt()                              │
│    ├─ pptx_loader.load_pptx()                            │
│    ├─ html_loader.load_html()                            │
│    ├─ json_loader.load_json()                            │
│    └─ xml_loader.load_xml()                              │
│                                                            │
│ Output: List of (page_number, text) tuples                │
│                                                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌─ CHUNKING (chunking.py) ──────────────────────────────────┐
│                                                            │
│ Input: List of (page_number, text) tuples                 │
│                                                            │
│ Process:                                                   │
│ ├─ Initialize RecursiveCharacterTextSplitter              │
│ │  └─ chunk_size: 500 characters (configurable)          │
│ │  └─ chunk_overlap: 100 characters (configurable)       │
│ │  └─ separators: ["\n\n", "\n", ". ", " ", ""]          │
│ │     (Split at best separator first)                     │
│ │                                                          │
│ ├─ For each page/section:                                 │
│ │  └─ Split text into chunks                              │
│ │  └─ Assign chunk_index (0, 1, 2, ...)                  │
│ │  └─ Track original page_number                          │
│ │                                                          │
│ Output: List of dicts:                                     │
│ └─ {                                                       │
│      "content": "chunk text...",                           │
│      "page_number": 1,                                     │
│      "chunk_index": 0                                      │
│    }                                                       │
│                                                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌─ EMBEDDING GENERATION (upload_service.py) ────────────────┐
│                                                            │
│ 1. Extract all chunk texts from chunks list               │
│                                                            │
│ 2. Encode chunks using Sentence Transformers              │
│    └─ Model: all-MiniLM-L6-v2                             │
│    └─ Batch size: 32 (for efficiency)                     │
│    └─ Output: Vector embeddings (384-dimensional)         │
│                                                            │
│ 3. Create metadata for each chunk:                        │
│    ├─ document_id (UUID - unique per upload)             │
│    ├─ filename (original filename)                        │
│    ├─ file_type (extension)                               │
│    ├─ upload_timestamp (ISO 8601)                         │
│    ├─ page_number                                         │
│    └─ chunk_index                                         │
│                                                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌─ VECTOR STORAGE (vectorstore.py) ────────────────────────┐
│                                                            │
│ 1. Connect to Weaviate instance                           │
│                                                            │
│ 2. Ensure schema exists (DocumentChunk class)             │
│    └─ Properties: content, document_id, filename,         │
│                   file_type, upload_timestamp,            │
│                   page_number, chunk_index                │
│                                                            │
│ 3. Batch insert all chunks with embeddings                │
│    ├─ Batch size: 10 chunks per batch                     │
│    ├─ data_object: chunk text + all metadata              │
│    ├─ vector: embedding (384-dimensional)                 │
│    └─ class_name: DocumentChunk                           │
│                                                            │
│ Output: Document indexed and searchable                    │
│                                                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌─ RESPONSE BACK TO FRONTEND ────────────────────────────────┐
│                                                            │
│ JSON Response (201 Created):                              │
│ {                                                          │
│   "document_id": "uuid-string",                           │
│   "filename": "report.pdf",                               │
│   "original_filename": "report.pdf",                      │
│   "file_type": "pdf",                                     │
│   "chunks_stored": 45                                     │
│ }                                                          │
│                                                            │
│ Frontend: Update document list, show success message       │
│                                                            │
└───────────────────────────────────────────────────────────┘

✅ Document Successfully Indexed and Ready for Querying
```

---

### Phase 3: Asking a Question Flow

**User Action:** User asks a question in the chat interface

```
┌─ FRONTEND (App.jsx) ─────────────────────────────────────┐
│                                                           │
│ 1. User types question and clicks send                    │
│ 2. Create new session if first message:                   │
│    └─ POST /api/sessions (with question as title)         │
│                                                           │
│ 3. Add user message to UI optimistically                  │
│                                                           │
│ 4. Send question to backend:                              │
│    └─ POST /api/sessions/{session_id}/ask                 │
│    └─ Body: { "question": "What is..." }                  │
│                                                           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─ BACKEND QUESTION HANDLER (app.py) ───────────────────────┐
│                                                            │
│ 1. Extract question from request                          │
│                                                            │
│ 2. Save user message to PostgreSQL:                       │
│    └─ INSERT into chat_messages (role='user', content)    │
│                                                            │
│ 3. Call retrieval_service.retrieve():                     │
│    ├─ Pass: question, embedding_model, weaviate_client    │
│    ├─ Optional: document_id (if user selected a doc)      │
│    └─ Returns: (chunks, retrieval_info)                   │
│                                                            │
│ 4. If chunks retrieved: Call ask_llm()                    │
│    └─ If no chunks: Return "No information found"         │
│                                                            │
│ 5. Save assistant message to PostgreSQL:                  │
│    └─ INSERT into chat_messages (role='assistant',        │
│                    content, sources, retrieval)           │
│                                                            │
│ 6. Return JSON response to frontend                       │
│                                                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─ RETRIEVAL SERVICE (retrieval_service.py) ────────────────┐
│                                                            │
│ Purpose: Find most relevant chunks, avoiding              │
│          cross-document contamination                     │
│                                                            │
│ TWO RETRIEVAL MODES:                                       │
│                                                            │
│ ═══════════════════════════════════════════════════════    │
│ MODE 1: EXPLICIT FILTER (document_id provided)            │
│ ═══════════════════════════════════════════════════════    │
│                                                            │
│ ├─ Create Weaviate WHERE filter:                          │
│ │  └─ document_id = {provided_id}                         │
│ │                                                          │
│ ├─ Convert question to embedding                          │
│ │  └─ Use same Sentence Transformers model                │
│ │  └─ Output: 384-dimensional vector                      │
│ │                                                          │
│ ├─ Query Weaviate with filter                             │
│ │  └─ Nearest-neighbor search in filtered space           │
│ │  └─ Return top_k=3 chunks (configurable)               │
│ │                                                          │
│ └─ Return chunks + retrieval_info:                        │
│    └─ mode: "explicit_filter"                             │
│    └─ document_id, filename                               │
│                                                            │
│ ═══════════════════════════════════════════════════════    │
│ MODE 2: AUTO ROUTING (no document_id)                     │
│ ═══════════════════════════════════════════════════════    │
│                                                            │
│ Step A: Candidate Pool Search                             │
│ ├─ Convert question to embedding                          │
│ ├─ Query across ALL documents                             │
│ ├─ Retrieve top_k=15 chunks (CANDIDATE_POOL_SIZE)        │
│ │  (Much larger than final k to ensure best doc found)    │
│ │                                                          │
│ Step B: Rank Documents by Best Evidence                   │
│ ├─ Group candidates by document_id                        │
│ ├─ For each document: find lowest distance (best chunk)   │
│ ├─ Rank documents by their best chunk distance           │
│ ├─ Reason: Even if doc has many chunks, quality of       │
│ │          evidence matters most (not quantity)           │
│ │                                                          │
│ Step C: Select Top Document                               │
│ ├─ Pick winner = document with best distance              │
│ ├─ Filter candidates: keep only chunks from winner        │
│ ├─ Return top_k=3 chunks from winner                      │
│ │                                                          │
│ └─ Return chunks + retrieval_info:                        │
│    ├─ mode: "auto_routed"                                 │
│    ├─ document_id, filename (winner)                      │
│    ├─ candidate_documents: [list of all docs + scores]    │
│    └─ (Used by frontend for "candidate docs" UI)          │
│                                                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─ WEAVIATE VECTOR SEARCH (vectorstore.py) ──────────────────┐
│                                                             │
│ 1. Receive query_vector (384-dimensional)                  │
│                                                             │
│ 2. Execute GraphQL query:                                  │
│    ├─ Operation: Get nearest neighbors                      │
│    ├─ Distance metric: cosine similarity                    │
│    ├─ Filter: WHERE clause (if provided)                   │
│    ├─ Limit: top_k chunks                                  │
│    └─ Return: distance + all metadata fields               │
│                                                             │
│ 3. Distance scoring:                                        │
│    ├─ Lower distance = more similar                         │
│    ├─ Distance ∈ [0, 2] for cosine (0=identical)          │
│    ├─ Frontend converts to relevance:                       │
│    │  relevance = max(0, min(1, 1 - distance))            │
│    └─ Displayed as % in UI                                 │
│                                                             │
│ 4. Return matched chunks with:                             │
│    ├─ content (text)                                       │
│    ├─ document_id                                          │
│    ├─ filename                                             │
│    ├─ file_type                                            │
│    ├─ page_number                                          │
│    ├─ chunk_index                                          │
│    ├─ _additional.distance (for scoring)                   │
│    └─ upload_timestamp                                     │
│                                                             │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─ LLM ANSWER GENERATION (app.py - ask_llm) ────────────────┐
│                                                            │
│ Input: question + retrieved_chunks                        │
│                                                            │
│ 1. Extract chunk contents                                 │
│                                                            │
│ 2. Build context string:                                  │
│    └─ context = join all chunk contents with "\n\n"       │
│                                                            │
│ 3. Construct prompt with system instructions:             │
│                                                            │
│ """You are a helpful assistant. Answer the question       │
│ using ONLY the context provided below. If the answer      │
│ is not in the context, say "I don't have enough           │
│ information to answer this."                              │
│                                                            │
│ Context:                                                   │
│ {context}                                                  │
│                                                            │
│ Question: {question}                                       │
│                                                            │
│ Answer:"""                                                │
│                                                            │
│ 4. Send to Hugging Face Inference API:                    │
│    ├─ Model: moonshotai/Kimi-K2-Instruct-0905             │
│    ├─ max_tokens: 300 (limit response length)             │
│    ├─ temperature: 0.3 (low = more deterministic)         │
│    └─ messages: [user role message with prompt]           │
│                                                            │
│ 5. Extract answer from completion                         │
│                                                            │
│ Output: Answer text (up to 300 tokens)                    │
│                                                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─ DATABASE PERSISTENCE (db.py) ────────────────────────────┐
│                                                            │
│ Store in PostgreSQL:                                       │
│                                                            │
│ chat_messages table:                                       │
│ ├─ id: UUID (generated)                                   │
│ ├─ session_id: UUID (from session)                        │
│ ├─ role: "assistant" (enum: user|assistant)              │
│ ├─ content: answer text                                   │
│ ├─ sources: JSONB array of chunks with:                   │
│ │  ├─ content                                             │
│ │  ├─ filename                                            │
│ │  ├─ page_number                                         │
│ │  ├─ chunk_index                                         │
│ │  ├─ distance (relevance score)                          │
│ │  └─ file_type                                           │
│ ├─ retrieval: JSONB object with:                          │
│ │  ├─ mode (explicit_filter | auto_routed | no_results)  │
│ │  ├─ document_id                                         │
│ │  ├─ filename                                            │
│ │  └─ candidate_documents (only if auto_routed)           │
│ └─ created_at: TIMESTAMPTZ (server time)                  │
│                                                            │
│ Benefits of storing retrieval_info & sources:             │
│ ├─ Reload conversation and see exact same evidence        │
│ ├─ Don't need to re-query Weaviate (faster)              │
│ ├─ Show "answered from document X" deterministically      │
│ └─ Debug which document was chosen                        │
│                                                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─ RESPONSE TO FRONTEND ────────────────────────────────────┐
│                                                            │
│ JSON Response (200 OK):                                   │
│ {                                                          │
│   "role": "assistant",                                    │
│   "content": "Based on the document...",                  │
│   "sources": [                                             │
│     {                                                      │
│       "content": "chunk text...",                          │
│       "filename": "report.pdf",                           │
│       "page_number": 1,                                    │
│       "chunk_index": 2,                                    │
│       "distance": 0.245,                                   │
│       "file_type": "pdf"                                   │
│     },                                                     │
│     ...                                                    │
│   ],                                                       │
│   "retrieval": {                                           │
│     "mode": "auto_routed",                                │
│     "document_id": "uuid",                                │
│     "filename": "report.pdf",                             │
│     "candidate_documents": [                              │
│       {                                                    │
│         "document_id": "uuid",                            │
│         "filename": "report.pdf",                         │
│         "best_distance": 0.245                            │
│       },                                                   │
│       ...                                                  │
│     ]                                                      │
│   }                                                        │
│ }                                                          │
│                                                            │
│ Frontend Processing:                                       │
│ ├─ Add assistant message to chat                           │
│ ├─ Render "Answered from report.pdf" badge                │
│ ├─ Expand evidence cards showing each chunk                │
│ ├─ Show relevance bar for each chunk (distance-based)      │
│ ├─ If auto_routed + multiple candidates:                  │
│ │  └─ Allow user to expand candidate list                 │
│ │  └─ Show document ranking and why winner was chosen     │
│ └─ Save message with full sources/retrieval data          │
│                                                            │
└───────────────────────────────────────────────────────────┘

✅ Question Answered and Logged
```

---

### Phase 4: Session Management

```
┌─ SESSION CREATION ────────────────────────────────────────┐
│                                                            │
│ When: First message in new chat                           │
│                                                            │
│ POST /api/sessions                                        │
│ Body: { "title": "What is..." }                           │
│                                                            │
│ Backend:                                                   │
│ ├─ Generate UUID for session_id                           │
│ ├─ Store in PostgreSQL chat_sessions table                │
│ ├─ title: question first 60 chars (optimistic)           │
│ ├─ created_at: now()                                      │
│ ├─ updated_at: now()                                      │
│ └─ Return: { "id": uuid, "title": "...", ... }           │
│                                                            │
└───────────────────────────────────────────────────────────┘

┌─ LOAD SESSION HISTORY ────────────────────────────────────┐
│                                                            │
│ GET /api/sessions/{session_id}/messages                   │
│                                                            │
│ Backend:                                                   │
│ ├─ Query chat_messages WHERE session_id = {id}            │
│ ├─ Order by created_at ASC                                │
│ ├─ Return all messages with sources & retrieval data      │
│ └─ Preserve original context from when answer was made    │
│                                                            │
│ Frontend:                                                  │
│ ├─ Render all messages in order                           │
│ ├─ Show evidence for each assistant message               │
│ ├─ Restore "answered from" badges                         │
│ └─ No need to re-query or re-generate                     │
│                                                            │
└───────────────────────────────────────────────────────────┘

┌─ DELETE SESSION ──────────────────────────────────────────┐
│                                                            │
│ DELETE /api/sessions/{session_id}                         │
│                                                            │
│ Backend:                                                   │
│ ├─ Find chat_sessions by id                               │
│ ├─ Delete cascade to chat_messages                        │
│ │  (PostgreSQL FOREIGN KEY ON DELETE CASCADE)             │
│ └─ Return: { "deleted": true, "id": uuid }               │
│                                                            │
│ Frontend:                                                  │
│ ├─ Remove session from sidebar list                       │
│ └─ If viewing that session, go to new chat                │
│                                                            │
└───────────────────────────────────────────────────────────┘
```

---

### Phase 5: Document Management

```
┌─ LIST ALL DOCUMENTS ──────────────────────────────────────┐
│                                                            │
│ GET /api/documents                                        │
│                                                            │
│ Backend (vectorstore.py):                                 │
│ ├─ Query Weaviate for all DocumentChunk records           │
│ │  └─ Limit: 10,000 (safety cap)                          │
│ │  └─ Fields: document_id, filename, file_type,           │
│ │                   upload_timestamp                      │
│ │                                                          │
│ ├─ Aggregate in Python:                                   │
│ │  └─ Group chunks by document_id                         │
│ │  └─ For each group:                                     │
│ │     ├─ document_id                                      │
│ │     ├─ filename                                         │
│ │     ├─ file_type                                        │
│ │     ├─ chunk_count (how many chunks in doc)             │
│ │     └─ upload_timestamp                                 │
│ │                                                          │
│ └─ Return: List of document summaries                     │
│                                                            │
│ Frontend:                                                  │
│ ├─ Display documents in sidebar                           │
│ ├─ Show filename, type, upload date                       │
│ ├─ Allow delete button for each                           │
│ └─ Optionally restrict question to single doc             │
│                                                            │
└───────────────────────────────────────────────────────────┘

┌─ DELETE DOCUMENT ────────────────────────────────────────┐
│                                                            │
│ DELETE /api/documents/{document_id}                       │
│                                                            │
│ Backend:                                                   │
│ ├─ Query Weaviate for all chunks with document_id         │
│ ├─ Delete them in batches                                 │
│ ├─ Reason: Weaviate doesn't have bulk-where-delete        │
│ │         (delete by arbitrary filter), so we:            │
│ │         1. Find matching objects                        │
│ │         2. Delete by their UUIDs                        │
│ │                                                          │
│ └─ Return: { "deleted": true, "count": N }               │
│                                                            │
│ Frontend:                                                  │
│ ├─ Remove document from list                              │
│ ├─ If user was filtering by this doc, clear filter        │
│ └─ Refresh available documents                            │
│                                                            │
│ Note: Doesn't delete chat history that references it      │
│       (Document may have been discussed previously)       │
│                                                            │
└───────────────────────────────────────────────────────────┘
```

---

## Detailed Module Breakdown

### 1. **config.py** - Central Configuration
```
Centralized settings for all modules:
├─ Paths: BASE_DIR, DOCUMENTS_DIR
├─ Weaviate: URL, class name
├─ Embedding: Model name (all-MiniLM-L6-v2)
├─ LLM: API token, model name, generation params
├─ Chunking: chunk_size (500), chunk_overlap (100)
├─ Allowed file types: 11 formats supported
└─ PostgreSQL: Connection parameters
```

### 2. **app.py** - Flask Backend API
```
Main application entry point:

Routes:
├─ GET /api/health
│  └─ Check backend, Weaviate, DB readiness
│
├─ POST /api/sessions
│  └─ Create new chat session
│
├─ GET /api/sessions
│  └─ List all chat sessions
│
├─ GET /api/sessions/{id}/messages
│  └─ Get chat history for a session
│
├─ DELETE /api/sessions/{id}
│  └─ Delete a session (cascade to messages)
│
├─ GET /api/documents
│  └─ List uploaded documents
│
├─ DELETE /api/documents/{id}
│  └─ Delete a document (all chunks)
│
├─ POST /api/upload
│  └─ Upload and ingest new documents
│
└─ POST /api/sessions/{id}/ask
   └─ Send question, get answer with sources

Core Functions:
├─ ask_llm(question, chunks)
│  └─ Generate answer using LLM
│
└─ _title_from_question(q)
   └─ Truncate question for session title
```

### 3. **document_loaders.py** - Format-Specific Parsing
```
Dispatcher for different file formats:

Supported Formats:
├─ PDF (pdf_loader)
├─ DOCX (docx_loader)
├─ XLSX/XLS (excel_loader)
├─ CSV (csv_loader)
├─ TXT/MD (txt_loader)
├─ PPTX (pptx_loader)
├─ HTML/HTM (html_loader)
├─ JSON (json_loader)
└─ XML (xml_loader)

Standard Output:
All loaders return: [(page_number, text), ...]
This uniform interface simplifies downstream processing
```

### 4. **chunking.py** - Text Segmentation
```
RecursiveCharacterTextSplitter:

Algorithm:
1. Try to split at sentence boundary ("\n\n")
2. If chunks still too large, split at line ("\n")
3. If still large, split at period (". ")
4. If still large, split at space (" ")
5. As last resort, split character-by-character ("")

Features:
├─ Configurable chunk_size (default: 500 chars)
├─ Configurable overlap (default: 100 chars)
│  └─ Overlap preserves context at chunk boundaries
└─ Metadata tracking:
   ├─ page_number (from source)
   ├─ chunk_index (0-based position in doc)
   └─ content (actual text)
```

### 5. **vectorstore.py** - Weaviate Integration
```
Vector Database Operations:

Schema Management:
├─ ensure_schema() - Create DocumentChunk class if needed
└─ Properties:
   ├─ content (text field)
   ├─ document_id (UUID, for grouping)
   ├─ filename
   ├─ file_type
   ├─ upload_timestamp
   ├─ page_number
   ├─ chunk_index
   └─ (vectors stored separately, not in class)

Insertion:
├─ insert_chunks(chunks, embeddings, metadata)
├─ Batch processing (size: 10)
└─ Stores both text and embedding vectors

Retrieval:
├─ query(query_vector, top_k, where_filter)
├─ Nearest-neighbor search
├─ Optional filtering by document_id
├─ Returns: top_k most similar chunks + distances
└─ Additional: distances for relevance scoring

Aggregation:
├─ list_documents() - Get unique documents
├─ Aggregates chunks by document_id
└─ Returns metadata summary per document
```

### 6. **retrieval_service.py** - Smart Document Routing
```
Two-Mode Retrieval Strategy:

MODE 1: Explicit Filter (user selects document)
├─ Weaviate WHERE filter: document_id = selected
├─ Vector search constrained to that document
├─ Return top_k chunks from that document only
└─ retrieval_info: { mode: "explicit_filter", ... }

MODE 2: Auto-Routing (no document selected) [DEFAULT]
├─ Step 1: Candidate Pool Search
│  ├─ Search across ALL documents
│  ├─ Return CANDIDATE_POOL_SIZE=15 top results
│  └─ Reason: Larger pool ensures best doc is found
│
├─ Step 2: Document Ranking
│  ├─ Group candidates by document_id
│  ├─ For each doc: find best_distance (single best chunk)
│  ├─ Sort docs by best_distance (lower = better)
│  └─ Why single best? Prevents good long docs from losing to
│     lucky similarity in unrelated short docs
│
├─ Step 3: Selection
│  ├─ Winner = document with best_distance
│  ├─ Filter: keep only winner's chunks from candidates
│  ├─ Return: top_k chunks from winner
│  └─ Result: Answer grounded in single coherent document
│
└─ retrieval_info: { mode: "auto_routed", 
                      candidate_documents: [...] }

Benefit: Prevents cross-document contamination
Example: If question is about contract terms, doesn't 
mix clauses from Contract A with clauses from Contract B
```

### 7. **upload_service.py** - Ingestion Pipeline
```
Full ingestion workflow:

1. Validate
   ├─ Check file extension against ALLOWED_EXTENSIONS
   └─ Reject unsupported formats

2. Sanitize & De-duplicate
   ├─ Use secure_filename() to prevent path traversal
   ├─ Check if filename already exists
   ├─ Append " (1)", " (2)", etc. if collision
   └─ Goal: Never silently overwrite

3. Parse Document
   ├─ Route to appropriate loader by extension
   ├─ Extract text + page numbers
   └─ Output: [(page_num, text), ...]

4. Chunk Text
   ├─ Split into ~500 char chunks
   ├─ Track page_number and chunk_index
   ├─ Add ~100 char overlap for context
   └─ Skip empty sections

5. Generate Embeddings
   ├─ Encode all chunks using Sentence Transformers
   ├─ Batch size: 32 (efficiency)
   ├─ Output: 384-dimensional vectors
   └─ Reuse same model as query time

6. Store in Weaviate
   ├─ Create document_id (UUID)
   ├─ Create metadata for each chunk
   ├─ Insert chunks + embeddings in batches
   └─ Enable vector search

Return: Document metadata (id, filename, chunk count, etc.)
```

### 8. **db.py** - PostgreSQL Persistence
```
Chat History Storage:

Schema:

chat_sessions:
├─ id (UUID PRIMARY KEY)
├─ title (TEXT, e.g., "What is..." - truncated question)
├─ created_at (TIMESTAMPTZ)
└─ updated_at (TIMESTAMPTZ)

chat_messages:
├─ id (UUID PRIMARY KEY)
├─ session_id (UUID, FOREIGN KEY → chat_sessions)
├─ role (TEXT: 'user' | 'assistant')
├─ content (TEXT: message text)
├─ sources (JSONB: array of chunks used for answer)
├─ retrieval (JSONB: routing info - which doc chosen)
└─ created_at (TIMESTAMPTZ)

Functions:
├─ init_db() - Create schema on startup
├─ get_pool() - Connection pooling
├─ create_session(title) - New conversation
├─ list_sessions() - All sessions
├─ get_session(id) - One session
├─ delete_session(id) - Remove conversation
├─ get_messages(session_id) - Chat history
├─ add_message(session_id, role, content, sources, retrieval)
│  └─ Store message with full context
└─ Connection pooling: 1-10 connections

Key Design: 
Storing sources + retrieval with each message means:
├─ Reload conversation = exact same UI display
├─ No need to re-query Weaviate
├─ Deterministic (not re-computed)
└─ Full audit trail of what was retrieved
```

---

## Data Flow Diagrams

### Document Upload → Search-Ready (Detailed)
```
┌─────────┐
│  File   │ (PDF, DOCX, etc.)
└────┬────┘
     │
     ▼
┌──────────────────┐
│ Format-Specific  │
│ Loader           │
└────┬─────────────┘
     │
     ▼ [(page_num, text), ...]
┌──────────────────┐
│ Chunking         │
│ (Recursive Split)│
└────┬─────────────┘
     │
     ▼ [{content, page_num, chunk_idx}, ...]
┌──────────────────┐
│ Embedding Model  │ (Sentence Transformers)
│ (Sentence Trans) │
└────┬─────────────┘
     │
     ▼ [384-D vectors, ...]
┌──────────────────┐
│ Weaviate         │
│ (Vector DB)      │
└──────────────────┘
     │
     └─ Index: Stored + Searchable ✓
```

### Question → Answer Flow (Detailed)
```
Question
   │
   ▼
[Embedding Model]
   │
   ▼ 384-D vector
[Weaviate Similarity Search]
   │
   ├─ Explicit Filter? 
   │  └─ Search only in selected doc
   │
   └─ Auto-Routing?
      ├─ Get top 15 candidates
      ├─ Group by document
      ├─ Rank docs by best chunk distance
      └─ Select winner, return top 3 chunks
   │
   ▼ [3 chunks] + [retrieval_info]
[LLM Prompt Builder]
   │
   ├─ System: "Answer using only context..."
   ├─ Context: Join chunk texts
   └─ Question: User's question
   │
   ▼ Prompt
[Hugging Face LLM API]
   │
   ▼ Answer text
[Store in PostgreSQL]
   │
   ├─ Message text
   ├─ Sources (chunks)
   └─ Retrieval info (which doc)
   │
   ▼ JSON Response
[Frontend - Render]
   │
   ├─ Answer text
   ├─ "Answered from X document"
   ├─ Evidence cards (chunks)
   └─ Relevance scores
```

---

## Key Design Patterns

### 1. **Separation of Concerns**
- **app.py**: HTTP routing only
- **vectorstore.py**: Weaviate operations only
- **db.py**: PostgreSQL operations only
- **retrieval_service.py**: Ranking logic only
- Each module has single responsibility

### 2. **Uniform Document Interface**
All loaders return: `[(page_number, text), ...]`
- Chunking, embedding, storage don't care about format
- Easy to add new file types without changing pipeline

### 3. **Metadata Tracking**
Every chunk stores:
- Source document identification
- Exact position in document
- Timestamp when indexed
- File type for UI labeling
- Enables accurate evidence display

### 4. **Smart Document Routing**
- **Auto-routing** prevents cross-document blending
- Groups candidates, ranks by best evidence
- Returns chunks from single coherent source
- Shows user which document was chosen

### 5. **Persistent Context**
- Stores `sources` and `retrieval` info with each message
- Reloading chat shows exact same evidence
- No need to re-query or re-compute
- Deterministic conversation history

### 6. **Graceful Degradation**
- Missing Weaviate → 503 Service Unavailable
- Unsupported format → Clear error message
- No search results → "I don't have information"
- Empty document → Clear validation error

---

## Configuration & Customization

All settings in **config.py**:

```python
# Chunking strategy
CHUNK_SIZE = 500           # Characters per chunk
CHUNK_OVERLAP = 100        # Overlap for context

# Embedding
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # 384-D vectors

# LLM
CHAT_MODEL = "moonshotai/Kimi-K2-Instruct-0905"
# Temperature: 0.3 (deterministic) to 1.0 (creative)

# Retrieval
CANDIDATE_POOL_SIZE = 15   # Candidates before ranking

# Files
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".csv",
    ".txt", ".pptx", ".md", ".html", ".htm", ".json", ".xml"
}
```

---

## Technology Integration Summary

| Component | Purpose | Technology |
|-----------|---------|-----------|
| **Web Framework** | HTTP routing, middleware | Flask |
| **Frontend** | UI, interactions | React + Vite |
| **Embeddings** | Convert text to vectors | Sentence Transformers |
| **Vector Search** | Find similar chunks | Weaviate |
| **LLM** | Generate answers | Hugging Face API |
| **Chat History** | Persist conversations | PostgreSQL |
| **Document Storage** | Save uploaded files | Filesystem |
| **Containerization** | Deployment, orchestration | Docker Compose |

---

## Conclusion

The RAG Chatbot implements a complete end-to-end document Q&A system with:

✅ **Multi-format support** - Handle PDFs, Office docs, spreadsheets, etc.
✅ **Intelligent retrieval** - Vector similarity + smart document routing
✅ **Context awareness** - Prevent cross-document contamination
✅ **Persistent history** - Store conversations with full provenance
✅ **Visual evidence** - Show user exactly which chunks were used
✅ **Scalable architecture** - Modular design, containerized deployment

The flow is: Upload → Parse → Chunk → Embed → Store → Search → Rank → Generate → Persist → Display
