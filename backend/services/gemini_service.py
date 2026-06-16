from dotenv import load_dotenv
import os, json
import google.generativeai as genai
from backend.config import Config

load_dotenv()
genai.configure(api_key=Config.GOOGLE_API_KEY)
_model = genai.GenerativeModel("gemini-2.5-flash")

TRIAGE_PROMPT = """
You are a hospital triage AI assistant helping doctors prioritize patients.

Patient Information:
- Name: {name}
- Age: {age} years old
- Reported condition/symptoms: {condition}

Assign a medical priority level based on clinical urgency using this scale:
5 = Critical  (immediately life-threatening: cardiac arrest, stroke,
               severe trauma, stopped breathing, unconscious)
4 = Serious   (severe but stable: compound fracture, fever above 104F,
               severe chest pain, difficulty breathing)
3 = Moderate  (needs timely attention: deep laceration needing stitches,
               persistent vomiting, moderate pain, high fever 101-104F)
2 = Mild      (non-urgent: sprained ankle, mild fever below 101F,
               minor infection, mild allergic reaction, no breathing issues)
1 = Minor     (routine/walk-in: common cold, skin rash, routine BP check,
               general wellness query)

CRITICAL INSTRUCTION: Respond ONLY with a single valid JSON object.
No markdown. No code fences. No explanation outside the JSON. Just raw JSON.

Required format (exactly):
{{"priority": <integer 1-5>, "label": "<Critical|Serious|Moderate|Mild|Minor>", "reasoning": "<exactly one sentence explaining your clinical assessment>"}}
"""

FALLBACK = {
    "priority" : 3,
    "label"    : "Moderate",
    "reasoning": "AI assessment unavailable — defaulting to Moderate. Please assess manually."
}

def suggest_priority(name: str, age: int, condition: str) -> dict:
    """
    Call Gemini API and return triage priority suggestion.
    NEVER raises — returns FALLBACK on any failure.

    Returns:
        dict with keys: priority (int 1-5), label (str), reasoning (str)
    """
    try:
        prompt   = TRIAGE_PROMPT.format(name=name, age=age, condition=condition)
        response = _model.generate_content(prompt)
        text     = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
        # Validate required keys and types
        assert "priority"  in parsed
        assert "label"     in parsed
        assert "reasoning" in parsed
        assert isinstance(parsed["priority"], int)
        assert 1 <= parsed["priority"] <= 5
        return parsed
    except Exception as e:
        print(f"[GeminiService] Error: {e}")
        return FALLBACK

def health_check() -> bool:
    """Return True if Gemini API responds. False on any error."""
    try:
        r = _model.generate_content("Reply with the single word: OK")
        return bool(r.text)
    except Exception:
        return False
