"""
LLMClassifier — Structured JSON classifier for O3Sigma alarm taxonomy.

Replaces ReasonClassifier as the primary classification engine.
Key improvements over ReasonClassifier:
  - JSON-only output (no fragile line-by-line regex of freetext LLM responses)
  - confidence score (0.0–1.0) — know when to trust the result
  - needs_review flag — auto-flagged when confidence < 0.7
  - Identical external interface: classify_reason(description, cause) -> dict
  - Same fallback chain: groq -> ollama -> heuristic

Wiring:
  pipeline.py passes LLMClassifier() into LocalLLMExtractor(classifier=...)
  ReasonClassifier remains available in local_llm_extractor.py as the legacy fallback.
"""

import re
import json
import os
from config import REASON_CLASSIFICATION_MODE, REASON_LEVEL_1_CATEGORIES

_PROMPT = """\
You are classifying an industrial alarm for the O3Sigma manufacturing platform.
Return ONLY a valid JSON object — no explanation, no markdown, no code fences.

Alarm description: {description}
Cause: {cause}

Classify into the following schema:
  reason_level_1: one of [{r1_options}]
  reason_level_2: Electrical | Mechanical | Sensor/Instrumentation | Software/Control | Process/Quality
  category_type:  Planned Downtime | Unplanned Downtime
  confidence:     float 0.0–1.0 representing your certainty
  needs_review:   true if confidence < 0.7, otherwise false

Rules:
- Planned Downtime = scheduled maintenance, cleaning (CIP), changeover, lubrication rounds
- Unplanned Downtime = all breakdowns, faults, unexpected stops
- confidence 1.0 = alarm text unambiguously maps to the category
- confidence 0.5 = ambiguous alarm text, classify by best guess

Return exactly this structure:
{{"reason_level_1": "...", "reason_level_2": "...", "category_type": "...", "confidence": 0.0, "needs_review": false}}"""


class LLMClassifier:
    """
    Primary O3Sigma alarm classifier.

    Interface-compatible with ReasonClassifier — both expose:
        classify_reason(description: str, cause: str = None) -> dict

    Extra fields returned (not in ReasonClassifier):
        confidence   float  — model certainty 0.0–1.0
        needs_review bool   — True when confidence < 0.7

    These extra fields pass through pipeline.py's item.update(clss) safely;
    AlarmRecord only reads the keys it knows about.
    """

    def __init__(self):
        self.mode = REASON_CLASSIFICATION_MODE
        self._cache: dict[str, dict] = {}

    # ── Public interface ────────────────────────────────────────────

    def classify_reason(self, description: str, cause: str = None) -> dict:
        """Classify one alarm. Results are cached by description text."""
        key = description.strip().lower()
        if key in self._cache:
            return self._cache[key]

        result = self._try_llm(description, cause)
        if result is None:
            result = self._heuristic(description, cause)

        self._cache[key] = result
        return result

    # ── LLM dispatch ────────────────────────────────────────────────

    def _try_llm(self, description: str, cause: str) -> dict | None:
        if self.mode == "groq":
            return self._groq(description, cause)
        if self.mode == "ollama":
            return self._ollama(description, cause)
        return None  # heuristic mode — skip LLM

    def _groq(self, description: str, cause: str) -> dict | None:
        try:
            from groq import Groq
            from config import GROQ_MODEL
            client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": self._build_prompt(description, cause)}],
                temperature=0.0,
                max_tokens=120,
            )
            result = self._parse(resp.choices[0].message.content)
            if result is None:
                print(f"[LLMClassifier/groq] JSON parse failed, falling back to ollama")
                return self._ollama(description, cause)
            return result
        except Exception as e:
            print(f"[LLMClassifier/groq] {e} — falling back to ollama")
            return self._ollama(description, cause)

    def _ollama(self, description: str, cause: str) -> dict | None:
        try:
            import ollama
            resp = ollama.generate(
                model=os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
                prompt=self._build_prompt(description, cause),
                options={"temperature": 0.0, "num_predict": 120},
            )
            result = self._parse(resp["response"])
            if result is None:
                print(f"[LLMClassifier/ollama] JSON parse failed, falling back to heuristic")
            return result
        except Exception as e:
            print(f"[LLMClassifier/ollama] {e} — falling back to heuristic")
            return None

    # ── Prompt & parser ─────────────────────────────────────────────

    def _build_prompt(self, description: str, cause: str) -> str:
        return _PROMPT.format(
            description=description,
            cause=cause or "not specified",
            r1_options=" | ".join(REASON_LEVEL_1_CATEGORIES),
        )

    def _parse(self, text: str) -> dict | None:
        """Extract and validate JSON from LLM response. Returns None on failure."""
        # Strip markdown code fences if present
        text = re.sub(r"```(?:json)?", "", text).strip()
        m = re.search(r"\{[\s\S]+\}", text)
        if not m:
            return None
        try:
            d = json.loads(m.group())
        except json.JSONDecodeError:
            return None

        required = {"reason_level_1", "reason_level_2", "category_type"}
        if not required.issubset(d.keys()):
            return None

        conf = float(d.get("confidence", 0.8))
        return {
            "reason_level_1": str(d["reason_level_1"]).strip(),
            "reason_level_2": str(d["reason_level_2"]).strip(),
            "category_type":  str(d["category_type"]).strip(),
            "confidence":     round(conf, 2),
            "needs_review":   bool(d.get("needs_review", conf < 0.7)),
        }

    # ── Heuristic fallback ──────────────────────────────────────────

    def _heuristic(self, description: str, cause: str) -> dict:
        """Keyword-based fallback — no LLM required. Always succeeds."""
        d = (description + " " + (cause or "")).lower()

        electrical = ["electric", "voltage", "inverter", "drive", "contactor", "fuse",
                      "relay", "arc", "wiring", "short circuit", "power supply", "amp"]
        instrumentation = ["sensor", "encoder", "limit switch", "photocell", "camera",
                           "probe", "detector", "vision"]
        software = ["plc", "software", "program", "hmi", "timeout", "communication",
                    "watchdog", "network", "bus", "fieldbus"]
        mechanical = ["jam", "belt", "bearing", "hydraulic", "valve", "pump", "gear",
                      "seal", "lubrication", "broken", "wear", "fracture", "pneumatic"]
        planned = ["maintenance", "cleaning", "changeover", "scheduled", "cip",
                   "lubrication round", "planned", "preventive"]

        if any(w in d for w in electrical):
            r2, conf = "Electrical", 0.75
        elif any(w in d for w in instrumentation):
            r2, conf = "Sensor/Instrumentation", 0.70
        elif any(w in d for w in software):
            r2, conf = "Software/Control", 0.70
        elif any(w in d for w in mechanical):
            r2, conf = "Mechanical", 0.75
        else:
            r2, conf = "Mechanical", 0.50

        cat = "Planned Downtime" if any(w in d for w in planned) else "Unplanned Downtime"

        return {
            "reason_level_1": "Basic Machine and Safety Faults",
            "reason_level_2": r2,
            "category_type":  cat,
            "confidence":     conf,
            "needs_review":   conf < 0.7,
        }
