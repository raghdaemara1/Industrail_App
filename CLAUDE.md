# CLAUDE.md — O3Sigma Bulk Upload AI Generator
## Architecture Reference · Free & Local Tool Stack for Demo

> This is the single source of truth for how this application is built.
> Read this before touching any file. Every tool listed here maps directly
> to actual code that exists in the repo. Nothing is theoretical.

---

## 1. What This App Does

O3Sigma requires a 13-tab Master Bulk Upload spreadsheet to configure each machine.
Engineers fill this manually from PDF manuals — fault guides, parameter sheets.

This app reads those PDFs, extracts every alarm and parameter record,
classifies them into O3Sigma's fixed taxonomy, and writes a ready-to-import .xlsx.

```
Input:   Machine PDF manual (fault list / parameter sheet / both)
Output:  13-tab Master Bulk Upload .xlsx  <- zero manual editing needed
Impact:  Days of work per machine -> under 2 minutes
```

---

## 2. Tool Replacement Map — Every Tool, Production vs Free

The app is built so every tool is swappable via .env. The pipeline logic never changes.

```
Layer                  Production Tool              Free / Local Replacement
-----                  ---------------              ------------------------
UI                     Streamlit                    Streamlit (already free)
PDF Parse (primary)    Docling / LlamaParse         pdfplumber (already in code)
PDF Parse (fallback)   —                            PyPDF2 (already in code)
LLM: Classify          GPT-4 / Cortex LLM           Ollama llama3.2:3b (local, free)
LLM: Extract           Platform structured API      Groq llama3-8b-8192 (free tier)
Embeddings             Snowflake Arctic Embed       sentence-transformers all-MiniLM-L6
Keyword Search         OpenSearch (AWS)             rank_bm25 (pure Python, in-memory)
Vector Search          Cortex / OpenSearch k-NN     chromadb (local persistent file)
Graph DB               Neo4j (managed)              networkx (in-memory graph)
Structured DB          MongoDB Atlas                MongoDB Community (local, free)
Object Store           Azure Blob                   Local filesystem (FILE_STORAGE_DIR)
Analytics / ML         Cortex AI (Snowflake)        scikit-learn + pandas (local)
Schema validation      Pydantic                     Pydantic (already free)
Excel export           openpyxl                     openpyxl (already free)
```

---

## 3. Project File Map — Actual Files in Repo

```
project/
├── app/
│   └── app.py                         <- Streamlit UI: upload, process, generate, history
│
├── core/
│   ├── pipeline.py                    <- BulkUploadPipeline: orchestrates all 6 steps
│   ├── pdf_processor.py               <- PDFProcessor: pdfplumber -> PyPDF2 fallback + MD5
│   ├── schemas.py                     <- AlarmRecord, ParameterRecord, ExtractionResult
│   ├── database.py                    <- DatabaseManager: MongoDB CRUD + indexes
│   ├── file_store.py                  <- FileStore: save/load raw PDF bytes
│   ├── spreadsheet_generator.py       <- SpreadsheetGenerator: openpyxl 13-tab workbook
│   └── phase_engine.py                <- PhaseEngine: builds tab payloads per phase
│
├── extractors/
│   ├── local_llm_extractor.py         <- LocalLLMExtractor + ReasonClassifier (Ollama)
│   └── parameter_specs_extractor.py   <- ParameterSpecsExtractor (regex + Ollama fallback)
│
├── search/                            <- NEW: add these files for demo search layer
│   ├── bm25_index.py                  <- rank_bm25 keyword index
│   ├── vector_index.py                <- sentence-transformers + chromadb
│   └── graph_index.py                 <- networkx alarm -> component -> machine graph
│
├── analytics/                         <- NEW: add for demo analytics
│   └── fault_analytics.py             <- scikit-learn: top faults, anomaly detection
│
├── config.py                          <- All env vars: OLLAMA_MODEL, MONGODB_URI, etc.
├── .env                               <- Local values (never commit)
├── requirements.txt
└── CLAUDE.md                          <- This file
```

---

## 4. End-to-End Pipeline — Step by Step

All steps run inside core/pipeline.py -> BulkUploadPipeline.process_pdf().

```
User uploads PDF  ->  app/app.py  ->  BulkUploadPipeline.process_pdf()
|
├── STEP 1 — FINGERPRINT
|     PDFProcessor computes MD5 of raw file bytes (hashlib)
|     DatabaseManager.get_processed_file(md5) checks processed_files collection
|     Cache HIT  -> load AlarmRecord[] + ParameterRecord[] from MongoDB -> return immediately
|     Cache MISS -> continue to Step 2
|     force_reprocess=True -> delete old cache -> re-run all steps
|
├── STEP 2 — PARSE TEXT
|     PDFProcessor.extract_text()
|       pdfplumber: reads page by page, extracts text with layout preserved
|       PyPDF2 fallback: runs if pdfplumber returns empty string
|     PDFProcessor.classify_content()
|       Keyword scoring (no LLM): flags has_alarms, has_parameters
|       Regex detects "Alarm \d+" or "Parameter" sections
|
├── STEP 3A — EXTRACT ALARMS  (if has_alarms=True)
|     LocalLLMExtractor.extract_alarms()
|       Splits text into chunks (chunk_size=4000 chars, paragraph-aware)
|       Regex-first: matches "Alarm 2088" then next-line description
|                    OR  "Alarm 2088 - Description on same line"
|       Ollama fallback: only when regex finds nothing in a chunk
|         Model: OLLAMA_MODEL (default: llama3.2:3b)
|         Prompt: structured JSON extraction prompt
|         Parse: extracts JSON array from response
|       Deduplicates by alarm_id within session
|     ReasonClassifier.classify_reason()
|       Per alarm: builds prompt with description + cause
|       Calls Ollama (temperature=0.1, max_tokens=128)
|       Parses response: "Reason 1: X", "Reason 2: Y", "Category: Z"
|       ClassificationCache: same description -> cached result, no re-call
|
├── STEP 3B — EXTRACT PARAMETERS  (if has_parameters=True)
|     ParameterSpecsExtractor.extract_parameters()
|       Regex: detects numeric value patterns + unit strings
|       Noise filters: skips lines containing Cause:/Reaction:/Remedy:
|       Prevents alarm text from leaking into parameter rows
|       Ollama fallback for enrichment (disabled by default)
|
├── STEP 4 — STORE IN MONGODB
|     db.save_alarms(result.alarms)
|       Upsert by (source_md5, alarm_id) -> no duplicates ever
|     db.save_parameters(result.parameters)
|       Upsert by (source_md5, description) -> no duplicates ever
|     db.register_processed_file(md5, filename, machine, ...)
|       Saves file_bytes into processed_files (for PDF download in History tab)
|
└── STEP 5 — GENERATE SPREADSHEET  (separate call from UI)
      PhaseEngine(machine, text, alarms, parameters).build(phases=[1,2,3])
        Builds dict: { "Downtime Configuration": [row_dicts], ... }
      SpreadsheetGenerator.create_workbook()
      SpreadsheetGenerator.populate_rows(sheet_name, rows) — per tab
      SpreadsheetGenerator.save() -> machine_KHS_2026-02-23.xlsx
      db.log_export(...) -> export_history collection
```

---

## 5. Data Models — Exact Fields

These Pydantic models live in core/schemas.py.
Every field name here maps to a MongoDB document key AND to an O3Sigma column.

### AlarmRecord
```python
class AlarmRecord(BaseModel):
    # Extracted from PDF
    alarm_id:        str            # "282" or "0282" — always STRING, preserve zeros
    description:     str            # "Drive fault — inverter overtemperature"
    cause:           Optional[str]  # "Ambient temperature too high"
    action:          Optional[str]  # "Check ventilation, clean heat exchanger"

    # Filled by ReasonClassifier
    reason_level_1:  Optional[str]  # One of 3 O3Sigma categories
    reason_level_2:  Optional[str]  # Subcategory string from LLM
    reason_level_3:  Optional[str]  # Copies cause field verbatim
    reason_level_4:  Optional[str]  # Copies action field verbatim
    category_type:   str = "Unplanned Downtime"

    # Added by pipeline
    machine:         Optional[str]  # "KHS_Filler"
    source_md5:      Optional[str]  # MD5 of the PDF that produced this record
    source_file:     Optional[str]  # "KHS_Filler_Alarms_v3.pdf"
    extracted_at:    Optional[datetime]
    manually_edited: bool = False
```

### ParameterRecord
```python
class ParameterRecord(BaseModel):
    parameter_code:  Optional[str]   # "P-001"
    description:     str             # "Clamping force" — unique key in doc
    section:         Optional[str]   # "3.2 Hydraulics"
    product_desc:    Optional[str]   # SKU / product variant

    # Tolerance band — all optional floats
    target:          Optional[float] # 2000.0
    unit:            Optional[str]   # "kN"
    lrl:             Optional[float] # Lower Rejection Limit
    lsl:             Optional[float] # Lower Specification Limit
    lwl:             Optional[float] # Lower Warning Limit
    uwl:             Optional[float] # Upper Warning Limit
    usl:             Optional[float] # Upper Specification Limit
    url:             Optional[float] # Upper Rejection Limit

    machine:         Optional[str]
    source_md5:      Optional[str]
    source_file:     Optional[str]
    extracted_at:    Optional[datetime]
```

### ExtractionResult (returned by pipeline to app.py)
```python
class ExtractionResult(BaseModel):
    success:         bool
    alarms:          List[AlarmRecord]
    parameters:      List[ParameterRecord]
    errors:          List[str]
    warnings:        List[str]
    debug_steps:     List[str]   # shown in UI "Phase Trace" expander
    timings:         dict        # shown in UI "Tool Timings" expander
    source_filename: Optional[str]
    source_md5:      Optional[str]
    source_text:     str = ""
```

---

## 6. MongoDB Collections — Exact Schema

### processed_files
```
md5                str      PRIMARY KEY — MD5 of raw PDF bytes
filename           str      original PDF filename
machine            str      machine name
processed_at       datetime
tabs_extracted     list     ["alarms", "parameters"]
record_counts      dict     {"alarms": 120, "parameters": 45}
extraction_version str      must match EXTRACTION_VERSION env var
file_content       bytes    raw PDF bytes stored here for History download
```
Indexes: md5 (unique), machine, (machine, processed_at)

### alarms
```
source_md5         str      links to processed_files.md5
alarm_id           str      alarm code — string, preserves leading zeros
description        str
cause              str
action             str
reason_level_1     str      O3Sigma Reason 1
reason_level_2     str      O3Sigma Reason 2
reason_level_3     str      copy of cause
reason_level_4     str      copy of action
category_type      str      "Unplanned Downtime" | "Planned Downtime"
machine            str
source_file        str
extracted_at       datetime
```
Indexes: source_md5, (machine, alarm_id), (source_md5, alarm_id) UNIQUE

### parameters
```
source_md5         str
parameter_code     str
description        str      — unique key per document
section            str
product_desc       str
target, lrl, lsl, lwl, uwl, usl, url   float
unit               str
machine            str
source_file        str
extracted_at       datetime
```
Indexes: source_md5, (machine, description), (source_md5, description) UNIQUE

### export_history
```
machine            str
filename           str
tabs_exported      list
record_counts      dict
exported_at        datetime
```

---

## 7. O3Sigma Column Mapping — What Goes Where

### Downtime Configuration tab (from AlarmRecord)
```
O3Sigma column       <-  AlarmRecord field
"Machine *"          <-  .machine
"Reason 1 *"         <-  .reason_level_1     (from ReasonClassifier)
"Reason 2"           <-  .reason_level_2     (from ReasonClassifier)
"Reason 3"           <-  .reason_level_3     (= cause verbatim from PDF)
"Reason 4"           <-  .reason_level_4     (= action verbatim from PDF)
"Category Type *"    <-  .category_type      (from ReasonClassifier)
"Fault Code *"       <-  .alarm_id           (string, zfill(4) if needed)
"Fault Name *"       <-  .description        (verbatim from PDF)
```

### Parameter Specifications tab (from ParameterRecord)
```
O3Sigma column       <-  ParameterRecord field
"Machine *"          <-  .machine
"Parameter Desc *"   <-  .description
"Product Desc *"     <-  .product_desc
"LRL"                <-  .lrl
"LSL"                <-  .lsl
"LWL"                <-  .lwl
"Target"             <-  .target
"UWL"                <-  .uwl
"USL"                <-  .usl
"URL"                <-  .url
```

---

## 8. Reason Classification — The O3Sigma Taxonomy

These categories are NOT in the PDF — they are O3Sigma-specific.
Defined in config.py as REASON_LEVEL_1_CATEGORIES. Used by ReasonClassifier.

### Reason Level 1 (3 fixed options)
```
"Automation, Process and Specialized Alarms"
"Basic Machine and Safety Faults"
"Rinser, Capper and Advanced Safety"
```

### Reason Level 2 (free text from LLM, common values)
```
Electrical | Mechanical | Sensor/Instrumentation | Software/Control | Process/Quality
```

### Category Type (2 options, default: Unplanned Downtime)
```
"Unplanned Downtime"
"Planned Downtime"
```

### How classification actually works (from local_llm_extractor.py)
```
ReasonClassifier.classify_reason(description, cause)
|
├── ClassificationCache.get(description) -> return if cached
|
├── Build prompt:
|     "Alarm Description: {description}"
|     "Cause: {cause}"
|     "Available Reason Level 1 categories: {REASON_LEVEL_1_CATEGORIES}"
|     "Respond in this EXACT format:"
|     "Reason 1: [category]"
|     "Reason 2: [subcategory]"
|     "Category: [Planned/Unplanned]"
|
├── Call ollama.generate(model, prompt, temperature=0.1, num_predict=128)
|
├── Parse response with regex:
|     r'Reason 1:\s*(.+?)(?:\n|$)'
|     r'Reason 2:\s*(.+?)(?:\n|$)'
|     r'Category:\s*(.+?)(?:\n|$)'
|
└── ClassificationCache.set(description, result)
      key = description.strip().lower()
      Same text -> same result every time, no LLM re-call
```

---

## 9. Free Tool Replacement — Exact Code to Add

### 9.1  Groq (replaces Ollama when not installed or for faster demo)

Free tier at console.groq.com — no credit card, 14,400 requests/day on free plan.

```python
# Add to extractors/local_llm_extractor.py

from groq import Groq

class GroqClassifier:
    """Drop-in replacement for ReasonClassifier using Groq free tier."""

    MODEL = "llama3-8b-8192"  # free, fast, good at short classification prompts

    def __init__(self):
        import os
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.cache = ClassificationCache()  # reuse existing cache class

    def classify_reason(self, description: str, cause: str = None) -> dict:
        cached = self.cache.get(description)
        if cached:
            return cached

        prompt = (
            f"Classify this industrial alarm. Respond ONLY in this exact format:\n"
            f"Reason 1: [one of: Automation Process and Specialized Alarms | "
            f"Basic Machine and Safety Faults | Rinser Capper and Advanced Safety]\n"
            f"Reason 2: [Electrical | Mechanical | Sensor/Instrumentation | "
            f"Software/Control | Process/Quality]\n"
            f"Category: [Planned Downtime | Unplanned Downtime]\n\n"
            f"Alarm: {description}\nCause: {cause or 'not specified'}"
        )

        response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=80,
        )
        text = response.choices[0].message.content
        result = self._parse(text)
        self.cache.set(description, result)
        return result

    def _parse(self, text: str) -> dict:
        import re
        r1 = re.search(r'Reason 1:\s*(.+)', text)
        r2 = re.search(r'Reason 2:\s*(.+)', text)
        cat = re.search(r'Category:\s*(.+)', text)
        return {
            "reason_level_1": r1.group(1).strip() if r1
                              else "Basic Machine and Safety Faults",
            "reason_level_2": r2.group(1).strip() if r2 else "Mechanical",
            "category_type":  "Planned Downtime"
                              if cat and "planned" in cat.group(1).lower()
                              and "unplanned" not in cat.group(1).lower()
                              else "Unplanned Downtime",
        }
```

To activate: set REASON_CLASSIFICATION_MODE=groq in .env and add GROQ_API_KEY=gsk_...

---

### 9.2  rank_bm25 (replaces OpenSearch for keyword search)

```python
# search/bm25_index.py  — create this file
from rank_bm25 import BM25Okapi

class BM25AlarmIndex:
    """
    In-memory BM25 keyword index.
    Same mathematical algorithm as OpenSearch BM25.
    No server, no install beyond pip install rank_bm25.
    """

    def __init__(self):
        self.corpus: list = []       # tokenized text per document
        self.alarm_ids: list = []    # parallel list of alarm_id strings
        self.bm25 = None

    def build(self, alarm_records: list):
        """Build index from alarm records loaded from MongoDB."""
        self.corpus = []
        self.alarm_ids = []
        for r in alarm_records:
            text = f"{r.get('description','')} {r.get('cause','')}"
            self.corpus.append(text.lower().split())
            self.alarm_ids.append(r["alarm_id"])
        self.bm25 = BM25Okapi(self.corpus)

    def search(self, query: str, top_k: int = 10) -> list:
        """Returns list of alarm_ids ranked by BM25 score."""
        if not self.bm25:
            return []
        scores = self.bm25.get_scores(query.lower().split())
        ranked = sorted(zip(self.alarm_ids, scores),
                        key=lambda x: x[1], reverse=True)
        return [aid for aid, score in ranked[:top_k] if score > 0]


# Usage:
# idx = BM25AlarmIndex()
# idx.build(list(db.alarms.find({"machine": "KHS_Filler"})))
# idx.search("inverter overtemperature")  ->  ["282", "310", ...]
# idx.search("alarm 282")                ->  ["282"] ranked first
```

Why BM25 works here: alarm codes like "alarm 282" or "inverter fault" are
exact-word queries. BM25 ranks documents containing those exact words highest.
This is the identical algorithm OpenSearch uses — just without the server.

---

### 9.3  sentence-transformers + chromadb (replaces Cortex vector search)

```python
# search/vector_index.py  — create this file
from sentence_transformers import SentenceTransformer
import chromadb

class VectorAlarmIndex:
    """
    Local semantic search.
    all-MiniLM-L6-v2: 80MB model, runs on CPU, 384-dimensional vectors.
    chromadb: persists to local disk, no server required.
    Finds alarms by MEANING, not by exact words.
    """

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        client = chromadb.PersistentClient(path=persist_dir)
        self.collection = client.get_or_create_collection(
            name="alarms",
            metadata={"hnsw:space": "cosine"}
        )

    def add_alarms(self, alarm_records: list):
        """Embed and store alarm records. Safe to call multiple times (upsert)."""
        for r in alarm_records:
            text = f"{r.get('description','')} {r.get('cause','')}"
            vector = self.model.encode(text).tolist()
            self.collection.upsert(
                ids=[f"{r.get('machine','x')}_{r['alarm_id']}"],
                documents=[text],
                embeddings=[vector],
                metadatas=[{
                    "alarm_id": r["alarm_id"],
                    "machine":  r.get("machine", ""),
                    "reason_2": r.get("reason_level_2", ""),
                }]
            )

    def search(self, query: str, top_k: int = 10,
               machine: str = None) -> list:
        """Semantic search — finds by meaning, not exact words."""
        vector = self.model.encode(query).tolist()
        where = {"machine": machine} if machine else None
        results = self.collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            where=where,
            include=["metadatas", "distances"]
        )
        return [
            {"alarm_id": m["alarm_id"], "score": round(1 - d, 3)}
            for m, d in zip(results["metadatas"][0], results["distances"][0])
        ]


# Usage:
# idx = VectorAlarmIndex()
# idx.add_alarms(list(db.alarms.find({"machine": "KHS_Filler"})))
#
# Keyword search would miss this — vector search finds it:
# idx.search("overheating problem in drive")
# -> returns alarm 282 (inverter overtemperature) with no word overlap
```

---

### 9.4  networkx (replaces Neo4j for relationship queries)

```python
# search/graph_index.py  — create this file
import networkx as nx
import re

COMPONENT_PATTERN = re.compile(
    r'\b(inverter|motor|servo|sensor|encoder|valve|pump|'
    r'bearing|seal|gear|belt|conveyor|drive|plc|hmi|camera)\b',
    re.IGNORECASE
)

class AlarmGraph:
    """
    In-memory directed graph: Alarm -> Component -> Machine.
    Answers relationship queries that MongoDB cannot:
    "which alarms involve the inverter?"
    "what components do alarm 282 and alarm 310 share?"
    "which component appears in the most alarms?"
    """

    def __init__(self):
        self.G = nx.DiGraph()

    def build(self, alarm_records: list):
        for r in alarm_records:
            aid     = r["alarm_id"]
            machine = r.get("machine", "unknown")

            self.G.add_node(aid,     type="alarm",
                            description=r.get("description",""),
                            reason_2=r.get("reason_level_2",""))
            self.G.add_node(machine, type="machine")
            self.G.add_edge(aid, machine, relation="BELONGS_TO")

            # Extract component names from cause text using regex
            for component in COMPONENT_PATTERN.findall(r.get("cause","") or ""):
                c = component.lower()
                self.G.add_node(c, type="component")
                self.G.add_edge(aid, c, relation="CAUSES")

    def alarms_for_machine(self, machine: str) -> list:
        return [n for n in self.G.predecessors(machine)
                if self.G.nodes[n].get("type") == "alarm"]

    def alarms_for_component(self, component: str) -> list:
        return [n for n in self.G.predecessors(component)
                if self.G.nodes[n].get("type") == "alarm"]

    def shared_components(self, alarm_a: str, alarm_b: str) -> list:
        """Components involved in BOTH alarms — useful for root cause analysis."""
        return list(set(self.G.successors(alarm_a)) & set(self.G.successors(alarm_b)))

    def component_risk_ranking(self) -> list:
        """Components sorted by number of alarms — maintenance priority."""
        comps = [
            (node, self.G.in_degree(node))
            for node, data in self.G.nodes(data=True)
            if data.get("type") == "component"
        ]
        return sorted(comps, key=lambda x: x[1], reverse=True)


# Usage:
# g = AlarmGraph()
# g.build(list(db.alarms.find({"machine": "KHS_Filler"})))
# g.alarms_for_component("inverter")      -> ["282", "310", "445"]
# g.component_risk_ranking()              -> [("inverter", 12), ("motor", 8), ...]
```

---

### 9.5  scikit-learn + pandas (replaces Cortex Analytics)

```python
# analytics/fault_analytics.py  — create this file
import pandas as pd
from sklearn.ensemble import IsolationForest

class FaultAnalytics:
    """
    Local analytics on alarm records already stored in MongoDB.
    Replaces Cortex AI analytics for demo purposes.
    All models run on CPU using data already in your local MongoDB.
    """

    def __init__(self, alarm_records: list):
        self.df = pd.DataFrame(alarm_records)

    def top_fault_categories(self, machine: str = None,
                             top_n: int = 10) -> list:
        """Most common Reason1 + Reason2 combinations for this machine."""
        df = self.df[self.df["machine"] == machine] if machine else self.df
        counts = (
            df.groupby(["reason_level_1", "reason_level_2"])
              .size()
              .reset_index(name="count")
              .sort_values("count", ascending=False)
              .head(top_n)
        )
        return counts.to_dict("records")

    def anomalous_machines(self) -> list:
        """
        Machines with unusually high alarm counts vs all others.
        IsolationForest flags statistical outliers automatically.
        Returns machine names flagged as anomalous.
        """
        counts = self.df.groupby("machine").size().reset_index(name="count")
        if len(counts) < 3:
            return []
        model = IsolationForest(contamination=0.1, random_state=42)
        counts["anomaly"] = model.fit_predict(counts[["count"]])
        return counts[counts["anomaly"] == -1]["machine"].tolist()

    def unclassified_alarms(self) -> list:
        """Alarm IDs where reason_level_1 is None — need manual review."""
        return self.df[self.df["reason_level_1"].isna()]["alarm_id"].tolist()

    def electrical_fault_rate(self, machine: str = None) -> float:
        """% of alarms classified as Electrical — wiring quality indicator."""
        df = self.df[self.df["machine"] == machine] if machine else self.df
        if len(df) == 0:
            return 0.0
        elec = df["reason_level_2"].str.contains(
            "electrical", case=False, na=False).sum()
        return round(elec / len(df) * 100, 1)

    def monthly_alarm_trend(self, machine: str = None) -> dict:
        """Alarm count per month — detect seasonal patterns or spikes."""
        df = self.df[self.df["machine"] == machine] if machine else self.df
        df = df.copy()
        df["month"] = pd.to_datetime(df["extracted_at"]).dt.to_period("M")
        counts = df.groupby("month").size()
        return {str(k): int(v) for k, v in counts.items()}


# Usage:
# alarms = list(db.alarms.find({}))
# analytics = FaultAnalytics(alarms)
# analytics.top_fault_categories("KHS_Filler")
# analytics.anomalous_machines()
# analytics.unclassified_alarms()
# analytics.electrical_fault_rate("KHS_Filler")
```

---

### 9.6  Local filesystem (replaces Azure Blob — already in code)

Already implemented in core/database.py.
register_processed_file() stores file_bytes directly in the processed_files document.
The History tab in app.py reads it back for the PDF download button.

For very large PDFs (>16MB MongoDB document limit), use FILE_STORAGE_DIR:

```python
# core/file_store.py  — controlled by FILE_STORAGE_BACKEND env var
# "local"  -> saves to FILE_STORAGE_DIR/md5[:2]/md5.pdf
# "azure"  -> saves to Azure Blob container (requires connection string)
```

---

## 10. Environment Variables — Complete .env Reference

```env
# ── APP ──────────────────────────────────────────────────────────────
DEFAULT_MACHINE=KHS_Filler
OUTPUT_DIR=./output
EXTRACTION_VERSION=v4-parameter-noise-filter

# ── MONGODB (local Community — free) ─────────────────────────────────
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=o3sigma_demo
# Atlas cloud (production):
# MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/

# ── PDF PARSING ───────────────────────────────────────────────────────
# pdfplumber is default and already integrated in core/pdf_processor.py
PDF_PARSER=pdfplumber
# USE_LLAMAPARSE=false
# LLAMA_CLOUD_API_KEY=llx-...     <- paid, skip for demo

# ── LLM: CLASSIFICATION (Reason 1/2) ─────────────────────────────────
# Options: heuristic | ollama | groq
REASON_CLASSIFICATION_MODE=heuristic   # start here — no LLM, regex only

# Ollama (local, free, best for air-gapped demo):
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434

# Groq (free tier, no install needed, requires API key):
# REASON_CLASSIFICATION_MODE=groq
# GROQ_API_KEY=gsk_...
# GROQ_MODEL=llama3-8b-8192

# ── LLM: EXTRACTION ───────────────────────────────────────────────────
ALARM_LLM_EXTRACTION=false         # true = slower but better for scanned PDFs
PARAMETER_LLM_ENRICHMENT=false     # uses OLLAMA_MODEL or GROQ when enabled

# ── FILE STORAGE ──────────────────────────────────────────────────────
FILE_STORAGE_BACKEND=local         # local | azure
FILE_STORAGE_DIR=./pdf_store
# AZURE_STORAGE_CONNECTION_STRING=...   <- skip for demo
# AZURE_CONTAINER_NAME=o3sigma-docs

# ── SEARCH LAYER (optional — for demo search feature) ─────────────────
SEARCH_BACKEND=memory              # memory=rank_bm25 | opensearch
# OPENSEARCH_HOST=https://...      <- skip for demo

# ── VECTOR SEARCH (optional) ─────────────────────────────────────────
VECTOR_BACKEND=chromadb            # chromadb | cortex
CHROMA_PERSIST_DIR=./chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2  # downloaded automatically on first run (~80MB)

# ── GRAPH (optional) ─────────────────────────────────────────────────
GRAPH_BACKEND=networkx             # networkx | neo4j
# NEO4J_URI=bolt://...             <- skip for demo

# ── ANALYTICS (optional) ─────────────────────────────────────────────
ANALYTICS_BACKEND=local            # local=scikit-learn | cortex
```

---

## 11. Installation — Demo From Zero

```bash
# 1. Python environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. MongoDB — choose one:
# macOS:
brew install mongodb-community && brew services start mongodb-community
# Docker (any OS):
docker run -d --name mongo -p 27017:27017 mongo:7

# 4. Ollama — only needed if REASON_CLASSIFICATION_MODE=ollama
# Download from https://ollama.com then:
ollama serve
ollama pull llama3.2:3b        # ~2GB, runs on CPU

# 5. Groq — alternative to Ollama (no local install)
# Sign up free at console.groq.com -> API Keys -> Create Key
# Add to .env: GROQ_API_KEY=gsk_...

# 6. Configure
cp .env.example .env
# Edit MONGODB_URI and REASON_CLASSIFICATION_MODE

# 7. Run
streamlit run app/app.py
```

### requirements.txt
```
# Already in app
streamlit>=1.35
pydantic>=2.5
python-dotenv
pdfplumber
PyPDF2
pymongo
openpyxl

# LLM backends
ollama>=0.4
groq

# Free search replacements
rank_bm25
sentence-transformers
chromadb

# Free analytics
scikit-learn
pandas

# Free graph
networkx
```

---

## 12. Configuration Decision Tree

```
What type of PDF do you have?
├── Clean digital PDF (text is selectable in PDF reader)?
│     PDF_PARSER=pdfplumber            <- default, already working, fastest
└── Scanned / image-based PDF?
      USE_LLAMAPARSE=true              <- paid, best accuracy
      OR ALARM_LLM_EXTRACTION=true     <- free via Groq/Ollama, slower

How should Reason 1/2 be classified?
├── Fastest, no setup, 80% accuracy on clean alarm text?
│     REASON_CLASSIFICATION_MODE=heuristic    <- regex only, default
├── Better accuracy, laptop with 8GB+ RAM available?
│     REASON_CLASSIFICATION_MODE=ollama       <- llama3.2:3b local
└── Best accuracy, have internet, minimal setup?
      REASON_CLASSIFICATION_MODE=groq         <- llama3-8b via API, free

Do you need to search across all alarms in the UI?
├── No, just generate .xlsx from uploaded PDF?
│     No action needed, search is optional
├── Yes, exact keyword search ("alarm 282", "inverter")?
│     Use search/bm25_index.py with rank_bm25
└── Yes, natural language search ("overheating alarms")?
      VECTOR_BACKEND=chromadb          <- local, sentence-transformers
```

---

## 13. Phase Roadmap — What Changes Per Phase

```
Phase 1 — NOW (current codebase)
  Tabs:    Machine Details, Downtime Configuration, Parameter Specifications, OEE
  Source:  pdfplumber extracts text, regex extracts records, Ollama/Groq classifies
  Demo:    All free tools — MongoDB local, Ollama or Groq, pdfplumber

Phase 2 — Q2 2026
  Tabs:    + Data Types, Machine Parameters, Product Configuration, Waste, User, Crew
  Source:  LlamaParse for complex PDFs; batch upload for multiple machines at once
  Change:  PhaseEngine._build_phase2() + new column schemas in schemas.py

Phase 3 — Q4 2026
  Tabs:    Full 13-tab output + all Checklist sheets
  Source:  Doc Intelligence platform API replaces pdfplumber entirely
           Platform delivers structured records via GET /alarms?machine=X
  Change:  pipeline.py Steps 2+3 replaced by single API call
           LocalLLMExtractor becomes redundant (platform does extraction)
```

---

## 14. Immutable Rules — Never Break These

```
RULE 1 — Fault Code is always a string, always.
  Write to .xlsx as:    str(alarm_id).zfill(4)
  Set cell format to:   "@"  (Excel text format)
  If written as int:    "0282" becomes 282. O3Sigma import will reject it.

RULE 2 — Upsert, never insert.
  Alarms:     update_one({source_md5, alarm_id},     $set, upsert=True)
  Parameters: update_one({source_md5, description},  $set, upsert=True)
  Re-uploading the same PDF must never create duplicate records.

RULE 3 — ClassificationCache prevents redundant LLM calls.
  Key:   description.strip().lower()
  Scope: in-memory per pipeline session (ClassificationCache dict)
  Same alarm description in 10 PDFs -> LLM called only once per session.

RULE 4 — Column schema lives in schemas.py only.
  PhaseEngine and SpreadsheetGenerator both import from schemas.py.
  Never hardcode column names in pipeline.py, phase_engine.py, or anywhere else.

RULE 5 — LLM is used ONLY for classification, not extraction.
  Extraction = reading alarm_id and description from PDF = regex work.
  Classification = assigning Reason 1/2 categories = LLM work.
  Using LLM for extraction is slow and produces inconsistent field names.

RULE 6 — Bump EXTRACTION_VERSION when logic changes.
  Any change to regex patterns or extraction behavior must bump this version.
  Pipeline checks: cached version != current version -> delete cache -> re-extract.
  This prevents old extraction logic results from being served from cache.

RULE 7 — Parameter noise filters must always run.
  Lines containing "Cause:", "Reaction:", "Remedy:" must be excluded from parameters.
  Alarm text must never appear in the Parameter Specifications tab.
  Filters are in ParameterSpecsExtractor — update PARAMETER_NOISE_PATTERNS in config.py.
```

---

## 15. Debugging — Common Issues and Exact Fixes

```
ISSUE: 0 alarms extracted after processing
WHERE: core/pdf_processor.py -> classify_content()
FIX:   Add print(has_alarms, text[:2000]) before extraction runs.
       Check if your PDF uses one of the two supported formats:
         Format A: "Alarm 2088\n  Drive fault description"  (multi-line)
         Format B: "Alarm 2088 - Drive fault description"   (single-line)
       If neither matches, add your pattern to _extract_with_regex()
       in extractors/local_llm_extractor.py.

ISSUE: Same alarm appears twice in MongoDB
WHERE: core/database.py -> save_alarms()
FIX:   Verify unique index exists:
         db.alarms.getIndexes()
         Should show index on {source_md5:1, alarm_id:1} with unique:true.
       If missing, recreate:
         db.alarms.createIndex({source_md5:1, alarm_id:1}, {unique:true})

ISSUE: Reason 1 is always the same default value
WHERE: extractors/local_llm_extractor.py -> ReasonClassifier._parse_classification()
FIX:   Add print(generated_text) right before the regex parsing.
       Check if Ollama is returning the expected format.
       Common fix: model is not following the "Reason 1: X" format.
       Try adding "Do not add any explanation." to the prompt.

ISSUE: Leading zeros missing from Fault Code in .xlsx
WHERE: core/spreadsheet_generator.py -> populate_rows()
FIX:   cell.value = str(alarm["alarm_id"]).zfill(4)
       cell.number_format = "@"
       Set the column format before writing header row, not after.

ISSUE: Ollama timeout during classification of large alarm list
WHERE: extractors/local_llm_extractor.py -> classify_reason()
FIX:   Option A: REASON_CLASSIFICATION_MODE=heuristic (no LLM, instant)
       Option B: Reduce num_predict from 128 to 64 in Ollama call options.
       Option C: Switch to REASON_CLASSIFICATION_MODE=groq (faster API).

ISSUE: chromadb fails with dimension mismatch on restart
WHERE: search/vector_index.py -> VectorAlarmIndex.__init__()
FIX:   Delete ./chroma_db directory entirely and rebuild the index.
       Happens when EMBEDDING_MODEL was changed between runs.
       Different models produce different vector dimensions — incompatible.

ISSUE: Parameter rows contain alarm cause/remedy text
WHERE: extractors/parameter_specs_extractor.py -> noise filtering
FIX:   Add the leaking text pattern to PARAMETER_NOISE_PATTERNS in config.py.
       The filter mechanism is already implemented — just add the new pattern.

ISSUE: Groq rate limit hit during demo with many unique alarms
WHERE: GroqClassifier.classify_reason()
FIX:   ClassificationCache is already deduplicating by description text.
       If still hitting limits, switch to REASON_CLASSIFICATION_MODE=heuristic
       for bulk runs. Free tier: 14,400 req/day, 30 req/min.
       Each unique alarm description = 1 Groq call (cached after that).
```

---

## 16. Adding a New Tab — Exact Steps

When Phase 2/3 tabs need to be added, follow this order exactly:

```
1. Add the column list to core/schemas.py:
   NEW_TAB_COLUMNS = ["Machine *", "Column A", "Column B", "Result"]

2. Add a build method to core/phase_engine.py:
   def _build_new_tab(self, tabs: dict) -> None:
       for record in self.alarms:          # or self.parameters
           tabs["New Tab Name"].append({
               "Machine *": record.get("machine") or self.machine,
               "Column A":  record.get("some_field", ""),
               "Column B":  "",
               "Result":    "",
           })

3. Register the empty tab and call the builder in PhaseEngine.build():
   tabs["New Tab Name"] = []
   if N in phase_set:
       self._build_new_tab(tabs)

4. Done. SpreadsheetGenerator.populate_rows() handles any tab name
   automatically. No changes to the generator, pipeline, or UI.
```
