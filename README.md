# O3Sigma Master Bulk Upload Generator

![O3Sigma Architecture](https://img.shields.io/badge/Architecture-Local%20%2F%20Free-blue)
![Python Version](https://img.shields.io/badge/Python-3.12+-green)

> A free, local, and extensible application designed to automate the process of converting machine PDF manuals (fault guides, parameter sheets) into a structured 13-tab O3Sigma Master Bulk Upload spreadsheet.

## 📖 Overview

O3Sigma requires a comprehensive 13-tab Master Bulk Upload spreadsheet to configure each machine. Traditionally, engineers fill this out manually by reading through PDF manuals. **This application fully automates that workflow.**

It reads PDF documents, extracts every alarm and parameter record, intelligently classifies them into O3Sigma's fixed taxonomy using local or cloud LLMs, and outputs a ready-to-import `.xlsx` file. What used to take days now takes under **2 minutes**.

## 🚀 Key Features

*   **PDF Parsing**: robust layout-preserving extraction (using `pdfplumber` and `PyPDF2`).
*   **Intelligent Extraction & Classification**: Regex-first extraction with LLM fallback (Ollama or Groq free tier) to handle complex, messy PDF data.
*   **Database Integration**: Local MongoDB storage ensures continuous history, deduplication via document fingerprinting, and quick retrievals.
*   **Advanced Data Search**:
    *   *Keyword Search*: BM25 in-memory index for exact match search.
    *   *Semantic Search*: Vector DB using ChromaDB and Sentence-Transformers.
    *   *Knowledge Graph*: Relationship mapping between alarms, components, and machines using NetworkX.
*   **Automated Excel Generation**: Writes directly to a structured 13-tab Excel workbook using `openpyxl`.
*   **Global Fault Analytics**: Built-in Pandas + Scikit-Learn tools to detect anomalies and show downtime rates.

---

## 🏗️ System Architecture & Workflow

### 1. High-Level Architecture Flow

This diagram illustrates how the system layers interact with each other.

```mermaid
graph TD
    UI[Streamlit UI] -->|Upload PDF| Pipeline[BulkUploadPipeline]
    
    subgraph Core Processing
        Pipeline --> Fingerprint[MD5 Deduplication]
        Fingerprint --> Parser[PDF Parser: pdfplumber/PyPDF2]
        Parser --> Extractor[Regex / LLM Extractor]
        Extractor --> Classifier[Reason Classifier]
    end
    
    subgraph Data Store
        Classifier --> DB[(MongoDB Storage)]
        Extractor --> DB
    end
    
    subgraph Output & Analytics
        DB --> SG[Spreadsheet Generator]
        DB --> Search[Search Layer: BM25 / Vector / Graph]
        DB --> Analytics[Fault Analytics]
        SG --> XLS[13-Tab Excel Download]
    end
```

### 2. End-to-End Execution Pipeline

Here is the exact step-by-step process of how an uploaded PDF turns into structured data.

```mermaid
sequenceDiagram
    actor User
    participant Streamlit as User Interface
    participant Pipeline as Processing Pipeline
    participant DB as MongoDB
    participant LLM as Ollama/Groq Model
    participant Excel as Spreadsheet Generator
    
    User->>Streamlit: Upload PDF Manual
    Streamlit->>Pipeline: start processing
    Pipeline->>DB: Check MD5 format cache
    alt Cache Hit
        DB-->>Pipeline: Return stored alarms/parameters
    else Cache Miss
        Pipeline->>Pipeline: Parse Text (pdfplumber)
        Pipeline->>Pipeline: Classify Section (Regex)
        opt Has Alarms
            Pipeline->>LLM: Extract & Classify Reasons
            LLM-->>Pipeline: Structured JSON & Categories
        end
        opt Has Parameters
            Pipeline->>Pipeline: Extract Specs & Filter Noise
        end
        Pipeline->>DB: Upsert Records (No Duplicates)
    end
    Pipeline->>Excel: Generate Phase Sheets
    Excel-->>Streamlit: Master_Bulk_Upload_Results.xlsx
    Streamlit-->>User: Provide Download Link
```

---

## ⚙️ Installation & Setup

You can run this entire stack locally with free tools.

### Prerequisites
* Python 3.12+ 
* Local MongoDB Community Edition (or Docker `mongo:7`)
* [Ollama](https://ollama.com/) installed locally (if using the local LLM option)

### Step-by-Step

1. **Clone and setup the environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

2. **Start MongoDB:**
   * **Windows/Mac**: Make sure the MongoDB service is running.
   * **Docker**: `docker run -d --name mongo -p 27017:27017 mongo:7`

3. **Start Ollama (Optional, for local extraction):**
   ```bash
   ollama serve
   ollama pull llama3.2:3b
   ```

4. **Environment Variables:**
   Copy the example config and edit it if necessary (or create `.env` from scratch).
   ```bash
   cp .env.example .env
   ```
   *Make sure `MONGODB_URI` points to your local DB or Atlas cluster.*

5. **Run the application:**
   ```bash
   streamlit run app/app.py
   ```

---

## 🛠️ Technology Stack Breakdown

The application is built so every production tool is completely swappable with a free/local equivalent via the `.env` configuration.

| Component | Production / Paid | Local / Free Replacement (Used in Demo) |
| :--- | :--- | :--- |
| **Frontend UI** | Streamlit | Streamlit |
| **PDF Parsing** | LlamaParse / Docling | pdfplumber + PyPDF2 fallback |
| **LLM Classification** | Cortex LLM / GPT-4 | Ollama (llama3.2:3b) or Groq API |
| **Structured Database**| MongoDB Atlas | MongoDB Community Edition |
| **File Object Store**| Azure Blob Storage | Local filesystem (`pdf_store`) |
| **Keyword Search** | AWS OpenSearch | `rank_bm25` (In-memory Python) |
| **Semantic Search**| Cortex / k-NN | `chromadb` + Sentence-Transformers |
| **Graph Database** | Neo4j | `networkx` |
| **Analytics Engine** | Snowflake Cortex AI | `scikit-learn` + `pandas` |

---

## 📝 Usage

1. **Upload & Process:** Open the app and go to the first tab. Set your target Machine Name, upload the PDF, and click **Extract Data & Generate**. The app will provide live trace logs of the extraction via LLM/Regex.
2. **Download Excel:** Once completed, a button to download the `Master_Bulk_Upload_Results.xlsx` file will appear.
3. **Search & Review:** Use the second tab to search your knowledge base of alarms (using Keyword, Semantic Vector, or Graph mappings).
4. **History & Analytics:** Head to the third tab to view previously uploaded files, delete cached memory, and review global fault analytics.

---

## 👤 Development & Maintenance

* **Configuration**: Key behaviors and thresholds are controlled in `.env` and `config.py`.
* **Adding new Excel Tabs**: Driven through `core/phase_engine.py` and defined within `schemas.py` without requiring massive structural changes.
