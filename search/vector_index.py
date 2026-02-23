from sentence_transformers import SentenceTransformer
import chromadb
from config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL
import os

class VectorAlarmIndex:
    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR):
        os.makedirs(persist_dir, exist_ok=True)
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=persist_dir)
        self.collection = client.get_or_create_collection(
            name="alarms",
            metadata={"hnsw:space": "cosine"}
        )

    def add_alarms(self, alarm_records: list):
        if not alarm_records: return
        ids = []
        docs = []
        embs = []
        metas = []
        for r in alarm_records:
            is_dict = isinstance(r, dict)
            desc = r.get('description','') if is_dict else r.description
            cause = r.get('cause','') if is_dict else r.cause
            machine = r.get('machine','') if is_dict else r.machine
            alarm_id = r.get('alarm_id','') if is_dict else r.alarm_id
            r2 = r.get('reason_level_2','') if is_dict else r.reason_level_2
            
            text = f"{desc} {cause}"
            vector = self.model.encode(text).tolist()
            ids.append(f"{machine or 'x'}_{alarm_id}")
            docs.append(text)
            embs.append(vector)
            metas.append({
                "alarm_id": alarm_id,
                "machine": machine or "",
                "reason_2": r2 or "",
            })
            
        self.collection.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)

    def search(self, query: str, top_k: int = 10, machine: str = None) -> list:
        vector = self.model.encode(query).tolist()
        where = {"machine": machine} if machine else None
        
        try:
            results = self.collection.query(
                query_embeddings=[vector],
                n_results=top_k,
                where=where,
                include=["metadatas", "distances"]
            )
            
            if not results["metadatas"] or not results["metadatas"][0]:
                return []
                
            out = []
            for m, d in zip(results["metadatas"][0], results["distances"][0]):
                out.append({"alarm_id": m["alarm_id"], "score": round(1 - d, 3)})
            return out
        except Exception as e:
            print(f"Error querying chroma: {e}")
            return []
