"""
LLM Pipeline
============
Multi-step NLP processing using Ollama (llama3.1:8b) for:
  1. Language detection (fasttext, <5ms)
  2. Hebrew / Arabic / Persian → English translation
  3. NER: Location / Weapon / Casualty / Unit extraction
  4. Event categorization (regex triage → LLM refinement)

Falls back gracefully to regex-only when Ollama is unavailable.
"""
from __future__ import annotations
import logging
import json
import re
import asyncio
from typing import Optional
import httpx

from ..models.event import ConflictIntel, LocationEntity, EventCategory
from .categorizer import categorize_message, extract_casualty_count, extract_weapon_mentions, extract_unit_mentions
from ..config import settings

logger = logging.getLogger("llm_pipeline")

# ── Language detection via fasttext ──────────────────────────────────
_FT_MODEL = None
_FT_MODEL_PATH = None

def _load_fasttext():
    global _FT_MODEL, _FT_MODEL_PATH
    from pathlib import Path
    model_path = Path(__file__).parent.parent / "data" / "models" / "lid.176.bin"
    if model_path.exists():
        try:
            import fasttext
            _FT_MODEL = fasttext.load_model(str(model_path))
            _FT_MODEL_PATH = str(model_path)
            logger.info(f"[LLM] fasttext model loaded from {model_path}")
        except Exception as e:
            logger.warning(f"[LLM] fasttext unavailable: {e}")
    else:
        logger.warning(f"[LLM] fasttext model not found at {model_path}. "
                        f"Download with: wget -O {model_path} "
                        f"https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin")


_load_fasttext()

# Languages that require translation before NLP processing
TRANSLATE_LANGUAGES = {"he", "ar", "fa", "ur", "iw"}

# ── Tactical NER system prompt ────────────────────────────────────────
# Injected as a preamble before every NER / classification call so the
# model is grounded in OSINT / military context for the Middle East.
TACTICAL_SYSTEM_PROMPT = """You are a military intelligence analyst specialising in Middle East conflict zones. Your task is to extract structured intelligence from open-source news reports with maximum accuracy.

THEATRE: Middle East (Israel/Gaza/West Bank, Lebanon/Hezbollah, Syria, Iraq, Iran, Yemen/Houthis, Red Sea, Persian Gulf, Strait of Hormuz).

RULES:
1. Extract ONLY information explicitly stated — never infer or hallucinate.
2. Locations must be specific (city, base, district, coordinates) not generic ("Middle East").
3. Weapon systems: use canonical NATO/IISS designations where possible (e.g. "Shahed-136 UCAV", "BM-21 Grad", "Iron Dome TMD").
4. Actor names: use full organisational names (e.g. "Islamic Revolutionary Guard Corps", "Al-Qassam Brigades", "IDF Southern Command").
5. Confidence in geo-coordinates: HIGH if article names a specific site, MEDIUM if a city/district, LOW if a country only.
6. Output ONLY the requested JSON — no prose, no markdown fencing, no explanation."""


def detect_language(text: str) -> str:
    """
    Detect the language of a text snippet.
    Returns ISO 639-1 language code (e.g. 'en', 'he', 'ar', 'fa').
    Returns 'en' as fallback if detection fails.
    """
    if not text:
        return "en"
    try:
        if _FT_MODEL:
            # Clean text for fasttext (remove newlines)
            clean = text.replace("\n", " ").strip()[:500]
            predictions = _FT_MODEL.predict(clean, k=1)
            label = predictions[0][0].replace("__label__", "")
            return label
    except Exception as e:
        logger.debug(f"[LLM] Language detection error: {e}")
    return "en"


async def translate_to_english(text: str, source_lang: str) -> str:
    """
    Translate text to English using Ollama.
    Returns the original text if translation fails or is not needed.
    """
    if source_lang == "en" or source_lang not in TRANSLATE_LANGUAGES:
        return text

    prompt = (
        f"Translate the following {source_lang} text to English. "
        f"Output ONLY the translation, no explanation:\n\n{text}"
    )
    result = await _call_ollama(prompt, max_tokens=500)
    if result:
        translated = result.strip()
        logger.debug(f"[LLM] Translated ({source_lang}→en): {translated[:80]}...")
        return translated
    return text


async def extract_entities_llm(translated_text: str) -> dict:
    """
    Use Ollama to extract named entities (locations, weapons, units, casualties).
    Prepends the tactical system prompt for improved Middle East NER accuracy.
    Returns a dict with extracted entities.
    """
    prompt = (
        f"{TACTICAL_SYSTEM_PROMPT}\n\n"
        "Extract intelligence entities from this conflict report. "
        "Return ONLY valid JSON with these exact keys:\n"
        "  locations   — list of specific place names (city, base, district, lat/lon if given)\n"
        "  weapons     — list of weapon/system designations (canonical names)\n"
        "  units       — list of military units, factions, or state actors\n"
        "  casualties  — integer total (killed + wounded) or null if not stated\n"
        "  is_confirmed — true only if the report explicitly uses 'confirmed', 'verified', or official attribution\n\n"
        "Example output:\n"
        "{\"locations\": [\"Nevatim Air Base\", \"Beer Sheva\"], "
        "\"weapons\": [\"F-35I Adir\", \"Iron Dome TMD\"], "
        "\"units\": [\"IDF Air Force\", \"Islamic Jihad\"], "
        "\"casualties\": 4, \"is_confirmed\": true}\n\n"
        f"Report:\n{translated_text[:900]}"
    )
    result = await _call_ollama(prompt, max_tokens=400)
    if result:
        try:
            # Extract JSON from response (may have markdown fencing)
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.debug(f"[LLM] JSON parse error in NER: {e}")
    return {}


async def classify_category_llm(text: str) -> tuple[EventCategory, float]:
    """
    LLM-based event category classification for low-confidence regex cases.
    Uses the tactical system prompt to improve Middle East context accuracy.
    Returns (EventCategory, confidence).
    """
    categories = [c.value for c in EventCategory]
    prompt = (
        f"{TACTICAL_SYSTEM_PROMPT}\n\n"
        f"Classify this conflict report into exactly ONE category. "
        f"Valid categories: {', '.join(categories)}. "
        f"Return ONLY a JSON object: {{\"category\": \"<category>\", \"confidence\": <0.0-1.0>}}\n\n"
        f"Report:\n{text[:600]}"
    )
    result = await _call_ollama(prompt, max_tokens=100)
    if result:
        try:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                cat_str = parsed.get("category", "unknown")
                conf = float(parsed.get("confidence", 0.5))
                try:
                    return EventCategory(cat_str), conf
                except ValueError:
                    pass
        except Exception as e:
            logger.debug(f"[LLM] Category parse error: {e}")
    return EventCategory.unknown, 0.3


async def _call_ollama(prompt: str, max_tokens: int = 400) -> Optional[str]:
    """
    Make a request to the local Ollama API.
    Returns the response text or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model":  settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.1,
                        "top_p": 0.9,
                    },
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
    except httpx.TimeoutException:
        logger.warning("[LLM] Ollama request timed out")
    except Exception as e:
        logger.warning(f"[LLM] Ollama unavailable: {e}")
    return None


async def process_message(raw_text: str, channel_name: str) -> ConflictIntel:
    """
    Full NLP pipeline for a raw Telegram message.
    Returns a populated ConflictIntel object.

    Pipeline steps:
      1. Language detection (fasttext)
      2. Translation if needed (Ollama)
      3. Regex categorization + entity extraction
      4. LLM refinement if regex confidence < 0.6
      5. Geocoding coordinates are resolved separately by the caller
    """
    intel = ConflictIntel(raw_text=raw_text)

    # Step 1 — Language detection
    lang = detect_language(raw_text)
    intel.source_language = lang

    # Step 2 — Translation
    if lang in TRANSLATE_LANGUAGES:
        translation = await translate_to_english(raw_text, lang)
    else:
        translation = raw_text
    intel.translation = translation

    # Step 3 — Regex triage
    category, regex_confidence = categorize_message(translation)
    intel.category = category
    intel.confidence = regex_confidence

    # Step 4 — LLM refinement for low-confidence or unknown categories
    if regex_confidence < 0.6 or category == EventCategory.unknown:
        llm_category, llm_confidence = await classify_category_llm(translation)
        # Only override if LLM is more confident
        if llm_confidence > regex_confidence:
            intel.category = llm_category
            intel.confidence = llm_confidence

    # Step 5 — Entity extraction
    # Fast regex extraction always runs
    intel.weapons_mentioned = extract_weapon_mentions(translation)
    intel.unit_mentions = extract_unit_mentions(translation)
    intel.casualty_count = extract_casualty_count(translation)

    # LLM entity extraction supplements regex for location names
    if intel.confidence >= 0.4:
        try:
            llm_entities = await extract_entities_llm(translation)
            if llm_entities:
                # Add LLM-extracted locations
                for loc_name in llm_entities.get("locations", []):
                    if loc_name and isinstance(loc_name, str):
                        intel.locations.append(LocationEntity(
                            raw_text=loc_name,
                            normalized=loc_name.strip(),
                        ))
                # Merge weapon/unit extractions
                llm_weapons = llm_entities.get("weapons", [])
                if llm_weapons:
                    intel.weapons_mentioned = list(set(intel.weapons_mentioned + llm_weapons))
                llm_units = llm_entities.get("units", [])
                if llm_units:
                    intel.unit_mentions = list(set(intel.unit_mentions + llm_units))
                # Only override casualty if LLM found one and regex didn't
                if intel.casualty_count is None and llm_entities.get("casualties"):
                    intel.casualty_count = llm_entities["casualties"]
                if llm_entities.get("is_confirmed"):
                    intel.is_confirmed = True
        except Exception as e:
            logger.debug(f"[LLM] Entity extraction error: {e}")

    # Deduplicate locations
    seen_locs = set()
    unique_locs = []
    for loc in intel.locations:
        key = (loc.normalized or loc.raw_text).lower()
        if key not in seen_locs:
            seen_locs.add(key)
            unique_locs.append(loc)
    intel.locations = unique_locs[:5]  # cap at 5 locations per message

    return intel


async def process_rss_entry(raw_text: str, feed_url: str) -> ConflictIntel:
    """
    NLP pipeline variant optimised for RSS news articles.

    Differences from process_message():
      • Always attempts language detection + translation (RSS can be Arabic/Hebrew).
      • LLM NER runs unconditionally (regex_confidence ≥ 0.3) because RSS prose
        is information-dense and worth the extra Ollama round-trip.
      • Uses the tactical system prompt in every Ollama call for better ME NER.
      • Sets source_language from fasttext; translation stored if non-English.

    Geocoding of extracted location names is handled by the caller (bravo_news.py)
    so it can apply the geo-tag fast-path first.
    """
    intel = ConflictIntel(raw_text=raw_text)

    # Step 1 — Language detection
    lang = detect_language(raw_text)
    intel.source_language = lang

    # Step 2 — Translation (RSS feeds can carry Arabic/Hebrew summaries)
    if lang in TRANSLATE_LANGUAGES:
        translation = await translate_to_english(raw_text, lang)
    else:
        translation = raw_text
    intel.translation = translation

    # Step 3 — Regex triage
    category, regex_confidence = categorize_message(translation)
    intel.category    = category
    intel.confidence  = regex_confidence

    # Step 4 — LLM classification (lower threshold for RSS — prose is richer)
    if regex_confidence < 0.6 or category == EventCategory.unknown:
        llm_category, llm_confidence = await classify_category_llm(translation)
        if llm_confidence > regex_confidence:
            intel.category   = llm_category
            intel.confidence = llm_confidence

    # Step 5 — Fast regex entity extraction
    intel.weapons_mentioned = extract_weapon_mentions(translation)
    intel.unit_mentions     = extract_unit_mentions(translation)
    intel.casualty_count    = extract_casualty_count(translation)

    # Step 6 — LLM NER (runs at lower threshold for RSS — quality prose justifies it)
    if intel.confidence >= 0.3:
        try:
            llm_entities = await extract_entities_llm(translation)
            if llm_entities:
                for loc_name in llm_entities.get("locations", []):
                    if loc_name and isinstance(loc_name, str):
                        intel.locations.append(LocationEntity(
                            raw_text=loc_name,
                            normalized=loc_name.strip(),
                        ))
                llm_weapons = llm_entities.get("weapons", [])
                if llm_weapons:
                    intel.weapons_mentioned = list(set(intel.weapons_mentioned + llm_weapons))
                llm_units = llm_entities.get("units", [])
                if llm_units:
                    intel.unit_mentions = list(set(intel.unit_mentions + llm_units))
                if intel.casualty_count is None and llm_entities.get("casualties"):
                    intel.casualty_count = llm_entities["casualties"]
                if llm_entities.get("is_confirmed"):
                    intel.is_confirmed = True
        except Exception as e:
            logger.debug(f"[LLM] RSS NER error: {e}")

    # Step 7 — Deduplicate locations
    seen_locs: set[str] = set()
    unique_locs: list[LocationEntity] = []
    for loc in intel.locations:
        key = (loc.normalized or loc.raw_text).lower()
        if key not in seen_locs:
            seen_locs.add(key)
            unique_locs.append(loc)
    intel.locations = unique_locs[:5]

    return intel
