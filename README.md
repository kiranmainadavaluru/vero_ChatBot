# RAG Chatbot - Retrieval-Augmented Generation Document Q&A System

A powerful document question-answering system that leverages vector embeddings and semantic search to provide intelligent answers based on your documents.

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Docker Setup](#docker-setup)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Project Overview

The **RAG Chatbot** is an intelligent document management and question-answering system that allows users to:
- Upload documents in multiple formats (PDF, DOCX, XLSX, CSV, TXT, PPTX, HTML, JSON, XML)
- Automatically process and chunk documents
- Create vector embeddings for semantic search
- Ask natural language questions about document content
- Receive answers with visual evidence and relevance scores
- Maintain multi-session chat history

The system uses **Retrieval-Augmented Generation (RAG)** to combine document retrieval with LLM capabilities for accurate, context-aware responses.

---

## ✨ Features

✅ **Multi-Format Document Support**
- PDF, DOCX, XLSX, CSV, TXT, PPTX, HTML, JSON, XML

✅ **Semantic Search**
- Vector-based document retrieval using Sentence Transformers
- Intelligent chunking and indexing

✅ **Intelligent Document Routing**
- Prevents mixing content from different documents
- Maintains document context integrity

✅ **Chat History**
- Multi-session persistence with PostgreSQL
- Track conversation history with relevance scores

✅ **Visual Evidence**
- Display relevant document chunks
- Show relevance scores for transparency

✅ **Real-time Management**
- Upload, delete, and manage documents on the fly
- Immediate indexing and availability

---

## 🛠️ Technology Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | Flask (Python) |
| Vector Database | Weaviate |
| SQL Database | PostgreSQL |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| LLM | Google Gemini (OpenAI-compatible API) |
| Document Processing | PyPDF2, python-docx, openpyxl, python-pptx, BeautifulSoup4 |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 18.3+ |
| Build Tool | Vite 7.1+ |
| Styling | CSS |
| HTTP Client | Fetch API |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Containerization | Docker & Docker Compose |
| Backend Server | Flask (port 5000) |
| Frontend Dev Server | Vite (port 5173) |
| Vector Store | Weaviate (port 8080) |
| Database | PostgreSQL (port 5432) |

---

## 📦 Prerequisites

Before you begin, ensure you have the following installed:

### Required
- **Python 3.9+** - [Download](https://www.python.org/downloads/)
- **Node.js 16+** - [Download](https://nodejs.org/)
- **Git** - [Download](https://git-scm.com/)
- **Docker & Docker Compose** (optional, for containerized deployment)

### Optional
- **PostgreSQL** (if not using Docker)
- **Weaviate** (if not using Docker)

### Check Installation
```bash
python --version
node --version
npm --version
git --version
```

---

## 🚀 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/rag-chatbot.git
cd rag-chatbot
```

### Step 2: Backend Setup

#### 2.1 Create Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 2.2 Install Backend Dependencies
```bash
cd rag_chatbot_app/backend
pip install -r requirements.txt
```

**Installed Packages:**
| Package | Version | Purpose |
|---------|---------|---------|
| Flask | Latest | Web framework |
| Flask-CORS | Latest | Cross-origin requests |
| python-dotenv | Latest | Environment variables |
| PyPDF2 | Latest | PDF processing |
| langchain-text-splitters | Latest | Document chunking |
| sentence-transformers | Latest | Text embeddings |
| weaviate-client | >=3.24, <4 | Vector database client |
| openai | Latest | Gemini access (OpenAI-compatible client) |
| python-docx | Latest | DOCX processing |
| openpyxl | Latest | Excel processing |
| xlrd | Latest | Excel reading |
| python-pptx | Latest | PowerPoint processing |
| beautifulsoup4 | Latest | HTML parsing |
| psycopg2-binary | Latest | PostgreSQL adapter |

### Step 3: Frontend Setup

```bash
cd ../frontend
npm install
```

---

## 📁 Project Structure

```
rag-chatbot/
├── README.md                              # Project documentation
├── RAG_CHATBOT_FLOW_EXPLANATION.md       # Detailed flow explanation
├── .gitignore                             # Git ignore rules
├── docker-compose.yml                     # Docker services configuration
│
└── rag_chatbot_app/
    ├── backend/
    │   ├── app.py                        # Flask main application
    │   ├── config.py                     # Configuration settings
    │   ├── requirements.txt               # Python dependencies
    │   │
    │   ├── Document Processing/
    │   ├── pdf_loader.py                 # PDF handling
    │   ├── docx_loader.py                # DOCX handling
    │   ├── excel_loader.py               # Excel handling
    │   ├── html_loader.py                # HTML handling
    │   ├── json_loader.py                # JSON handling
    │   ├── csv_loader.py                 # CSV handling
    │   ├── pptx_loader.py                # PowerPoint handling
    │   ├── txt_loader.py                 # Text handling
    │   ├── xml_loader.py                 # XML handling
    │   ├── document_loaders.py            # Document loader router
    │   │
    │   ├── Core Services/
    │   ├── chunking.py                   # Document chunking logic
    │   ├── vectorstore.py                # Weaviate integration
    │   ├── retrieval_service.py          # Semantic search service
    │   ├── upload_service.py             # Document upload handler
    │   ├── db.py                         # Database operations
    │   │
    │   └── documents/                    # Uploaded documents storage
    │       └── .gitkeep
    │
    └── frontend/
        ├── package.json                  # Node dependencies
        ├── vite.config.js                # Vite configuration
        ├── index.html                    # HTML entry point
        └── src/
            ├── App.jsx                   # Main React component
            ├── App.css                   # Styling
            └── main.jsx                  # React entry point
```

---

## ⚙️ Configuration

### Backend Configuration

Create a `.env` file in the `backend/` directory:

```env
# Flask Configuration
FLASK_ENV=development
DEBUG=True

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/rag_chatbot

# Weaviate Vector Database
WEAVIATE_URL=http://localhost:8080

# Gemini API (Google AI Studio - free key at https://aistudio.google.com/apikey)
GEMINI_API_KEY=your_gemini_api_key_here

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# LLM Model
LLM_MODEL=gemini-2.5-flash

# CORS Settings
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Frontend Configuration

The frontend communicates with the backend on `http://localhost:5000` by default. Update `src/App.jsx` if you need a different backend URL.

---

## ▶️ Running the Application

### Option 1: Local Development (Without Docker)

#### Terminal 1 - Backend
```bash
cd rag_chatbot_app/backend
.venv\Scripts\activate  # Windows
python app.py
# Server runs on http://localhost:5000
```

#### Terminal 2 - Frontend
```bash
cd rag_chatbot_app/frontend
npm run dev
# Server runs on http://localhost:5173
```

#### Terminal 3 - Services (if not using Docker)
You'll need to run Weaviate and PostgreSQL separately or use Docker Compose.

### Option 2: Using Docker Compose (Recommended)

```bash
# From project root
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Services:**
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:5000`
- Weaviate: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

---

## 🔌 API Endpoints

### Document Management
```
POST   /upload              - Upload a document
GET    /documents           - List all documents
DELETE /documents/<id>      - Delete a document
GET    /documents/<id>      - Get document details
```

### Chat & Retrieval
```
POST   /chat                - Send a message and get response
GET    /chat-history/<id>   - Get session chat history
DELETE /chat-history/<id>   - Clear session history
```

### Search
```
POST   /search              - Semantic search across documents
GET    /search/<query>      - Search with parameters
```

For detailed API documentation, see `RAG_CHATBOT_FLOW_EXPLANATION.md`

---

## 🐳 Docker Setup

### Prerequisites
- Docker Desktop installed and running

### Using Docker Compose

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down

# Remove volumes (clean database)
docker-compose down -v
```

### Services in Docker
- **Backend**: Python Flask app in container
- **Frontend**: React app served via Vite in container
- **Weaviate**: Vector database in container
- **PostgreSQL**: Relational database in container

---

## 🐛 Troubleshooting

### Backend Issues

#### Virtual Environment Not Activating
```bash
# Windows - If .venv\Scripts\activate doesn't work
.venv\Scripts\activate.ps1

# If PowerShell execution policy blocks it
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Missing Dependencies
```bash
# Reinstall all dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Port Already in Use
```bash
# Find process using port 5000
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # macOS/Linux

# Kill the process (Windows)
taskkill /PID <PID> /F
```

### Frontend Issues

#### Node Modules Issues
```bash
# Clear cache and reinstall
rm -r node_modules package-lock.json
npm install
```

#### Vite Build Errors
```bash
# Clear vite cache
rm -r .vite
npm run dev
```

### Database Issues

#### PostgreSQL Connection Error
```
Check DATABASE_URL in .env
Ensure PostgreSQL is running: docker-compose up postgres
```

#### Weaviate Connection Error
```
Check WEAVIATE_URL in .env
Ensure Weaviate is running: docker-compose up weaviate
```

### Docker Issues

#### Container Won't Start
```bash
# View detailed logs
docker-compose logs backend

# Rebuild without cache
docker-compose up --build --no-cache
```

---

## 📝 Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Backend changes in `rag_chatbot_app/backend/`
   - Frontend changes in `rag_chatbot_app/frontend/`

3. **Test your changes**
   ```bash
   # Test backend
   python -m pytest
   
   # Test frontend
   npm test
   ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "Add your feature"
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request on GitHub**

---

## 📚 Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Weaviate Docs](https://weaviate.io/developers/weaviate)
- [React Documentation](https://react.dev/)
- [Sentence Transformers](https://www.sbert.net/)
- [Langchain](https://js.langchain.com/)

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📧 Contact & Support

For issues and questions:
- Open an Issue on GitHub
- Contact: kiranmainadavaluru@gmail.com

---

**Last Updated:** 2026-07-03
**Version:** 1.0.0