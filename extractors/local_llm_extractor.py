import re
import ollama
from groq import Groq
import os
from config import REASON_CLASSIFICATION_MODE, REASON_LEVEL_1_CATEGORIES, OLLAMA_MODEL, GROQ_MODEL, GROQ_API_KEY # Need to adjust max_tokens in prompt

class ClassificationCache:
    def __init__(self):
        self.cache = {}
    def get(self, text):
        return self.cache.get(text.strip().lower())
    def set(self, text, result):
        self.cache[text.strip().lower()] = result

class ReasonClassifier:
    def __init__(self):
        self.mode = REASON_CLASSIFICATION_MODE
        self.cache = ClassificationCache()

        if self.mode == "groq":
            try:
                self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
            except:
                self.mode = "heuristic"
                print("Fallback to heuristic classification (no GROQ key)")
    
    def classify_reason(self, description: str, cause: str = None) -> dict:
        cached = self.cache.get(description)
        if cached:
            return cached

        if self.mode == "groq":
            return self._groq_classify(description, cause)
        elif self.mode == "ollama":
            return self._ollama_classify(description, cause)
        else:
            return self._heuristic_classify(description, cause)

    def _build_prompt(self, description, cause):
        return (
            f"Classify this industrial alarm. Respond ONLY in this exact format:\n"
            f"Reason 1: [{ ' | '.join(REASON_LEVEL_1_CATEGORIES) }]\n"
            f"Reason 2: [Electrical | Mechanical | Sensor/Instrumentation | "
            f"Software/Control | Process/Quality]\n"
            f"Category: [Planned Downtime | Unplanned Downtime]\n\n"
            f"Alarm: {description}\nCause: {cause or 'not specified'}\nDo not add any explanation."
        )
    
    def _parse(self, text: str) -> dict:
        r1 = re.search(r'Reason 1:\s*(.+)', text)
        r2 = re.search(r'Reason 2:\s*(.+)', text)
        cat = re.search(r'Category:\s*(.+)', text)
        return {
            "reason_level_1": r1.group(1).strip() if r1 else "Basic Machine and Safety Faults",
            "reason_level_2": r2.group(1).strip() if r2 else "Mechanical",
            "category_type":  "Planned Downtime" if cat and "planned" in cat.group(1).lower() and "unplanned" not in cat.group(1).lower() else "Unplanned Downtime",
        }

    def _groq_classify(self, description: str, cause: str) -> dict:
        try:
            prompt = self._build_prompt(description, cause)
            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=80,
            )
            text = response.choices[0].message.content
            result = self._parse(text)
            self.cache.set(description, result)
            return result
        except Exception as e:
            print(f"Groq API error fallback: {e}")
            return self._heuristic_classify(description, cause)

    def _ollama_classify(self, description: str, cause: str) -> dict:
        try:
            prompt = self._build_prompt(description, cause)
            response = ollama.generate(
                model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
                prompt=prompt,
                options={
                    "temperature": 0.1,
                    "num_predict": 128
                }
            )
            result = self._parse(response['response'])
            self.cache.set(description, result)
            return result
        except Exception as e:
            print(f"Ollama API error fallback: {e}")
            return self._heuristic_classify(description, cause)

    def _heuristic_classify(self, description: str, cause: str) -> dict:
        cat = "Basic Machine and Safety Faults"
        r2 = "Mechanical"
        desc_lower = (description + " " + (cause or "")).lower()
        
        electrical_words = ["electric", "voltage", "current", "drive", "inverter", "short circuit", "wire", "contactor", "spark", "arc", "encoder", "fuse", "relay", "power supply", "amp"]
        mechanical_words = ["jam", "wear", "broken", "loose", "fracture", "belt", "bearing", "pneumatic", "hydraulic", "valve", "pump", "gear", "seal", "lubrication", "friction"]
        instrumentation_words = ["sensor", "encoder", "limit switch", "photocell", "vision", "camera", "probe", "detector"]
        software_words = ["program", "software", "plc", "timeout", "hmi", "network", "communication loss", "watchdog"]

        if any(w in desc_lower for w in electrical_words):
            r2 = "Electrical"
        elif any(w in desc_lower for w in instrumentation_words):
            r2 = "Sensor/Instrumentation"
        elif any(w in desc_lower for w in software_words):
            r2 = "Software/Control"
        elif any(w in desc_lower for w in mechanical_words):
            r2 = "Mechanical"
            
        result = {
            "reason_level_1": cat,
            "reason_level_2": r2,
            "category_type": "Unplanned Downtime"
        }
        self.cache.set(description, result)
        return result

class LocalLLMExtractor:
    def __init__(self, classifier=None):
        # Accept an injected classifier (e.g. LLMClassifier from llm_extractor.py).
        # Falls back to ReasonClassifier when none is provided.
        self.classifier = classifier if classifier is not None else ReasonClassifier()
    def extract_alarms(self, text: str) -> list:
        alarms = []
        chunks = self._chunk_text(text)
        for chunk in chunks:
            extracted = self._extract_with_regex(chunk)
            if not extracted:
                if os.environ.get("ALARM_LLM_EXTRACTION", "false").lower() == "true":
                    extracted = self._extract_with_llm(chunk)
            for item in extracted:
                desc = item.get("description", "")
                cause = item.get("cause", "")
                clss = self.classifier.classify_reason(desc, cause)
                item.update(clss)
                alarms.append(item)
                
        # Deduplication handled downstream primarily or here based on alarm_id
        unique_alarms = {}
        for a in alarms:
            if a.get("alarm_id") not in unique_alarms:
                unique_alarms[a["alarm_id"]] = a
        return list(unique_alarms.values())

    def _chunk_text(self, text: str, chunk_size=4000) -> list:
        # Paragraph aware chunking
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for p in paragraphs:
            if set(p.strip()) == {""}: continue
            if len(current) + len(p) < chunk_size:
                current += p + "\n\n"
            else:
                if current: chunks.append(current)
                current = p + "\n\n"
        if current: chunks.append(current)
        return chunks

    def _extract_with_regex(self, chunk: str) -> list:
        alarms = []
        # Support format A and B from CLAUDE.md
        pattern = re.compile(
            r'^[ \t]*(?:Alarm|Error|Fault)[ \t]*[:\-]?[ \t]*(\d{1,5})[ \t\.\-\:]*(?:.*?)\n(.*?)(?:\n[ \t]*Cause:[ \t]*(.*?))?(?:\n[ \t]*(?:Reaction|Remedy|Action):[ \t]*(.*?))?(?=\n[ \t]*(?:Alarm|Error|Fault)[ \t]*[:\-]?[ \t]*\d{1,5}|\Z)',
            re.IGNORECASE | re.DOTALL | re.MULTILINE
        )
        for match in pattern.finditer(chunk):
            aid = match.group(1).strip()
            desc = match.group(2).strip()
            cause = match.group(3).strip() if match.group(3) else None
            action_text = match.group(4).strip() if match.group(4) else None
            if not desc: continue
            desc = desc.split('\n')[0] # often multiline leaks, take just first
            alarms.append({"alarm_id": aid, "description": desc, "cause": cause, "action": action_text})
        return alarms

    def _extract_with_llm(self, chunk: str) -> list:
        # LLM fallback skipping
        return []
