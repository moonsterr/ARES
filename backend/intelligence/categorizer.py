"""
Event Categorizer
=================
Fast regex-based pre-filter for message categorization.
Falls back to LLM if regex confidence is low.

Returns an EventCategory + confidence score without needing
a full LLM round trip for clear-cut messages.
"""
from __future__ import annotations
import re
import logging
from ..models.event import EventCategory

logger = logging.getLogger("categorizer")

# ── Regex patterns for each category ─────────────────────────────────
# Patterns are applied against lowercased English text.
# The `score` weight is used as initial confidence.

CATEGORY_PATTERNS = [
    {
        "category": EventCategory.air_alert,
        "patterns": [
            r"\bair\s+(raid|alert|attack|strike|defense|assault)\b",
            r"\bmissile\s+(launch|strike|barrage|salvo)\b",
            r"\bdrone\s+(strike|attack|swarm|intercept)\b",
            r"\bair\s+siren\b",
            r"\bred\s+alert\b",
            r"\bincoming\s+(missile|rocket|mortar)\b",
            r"\biron\s+dome\b",
            r"\bintercepted?\b.{0,30}\b(missile|rocket|uav|drone)\b",
            r"\b(f-?35|f-?16|su-?35|mig-?\d+)\b.{0,50}\b(strike|attack|bombing)\b",
        ],
        "score": 0.82,
    },
    {
        "category": EventCategory.ground_strike,
        "patterns": [
            r"\b(artillery|mortar|tank|idf|irgc)\s+(fire|shelling|bombardment|strike)\b",
            r"\bground\s+(strike|attack|assault|offensive)\b",
            r"\bbuilding.{0,20}(destroyed|hit|struck|bombed)\b",
            r"\bexplosion.{0,20}(reported|heard|confirmed)\b",
            r"\bhamas.{0,30}(attack|raid|offensive)\b",
            r"\bhezbollah.{0,30}(attack|fire|launched)\b",
            r"\bhouthi.{0,30}(attack|strike|launch)\b",
            r"\bbomb\s+exploded?\b",
            r"\bIED\b",
        ],
        "score": 0.78,
    },
    {
        "category": EventCategory.troop_movement,
        "patterns": [
            r"\btroop\s+(movement|deployment|withdrawal|advance|retreat)\b",
            r"\bground\s+(forces|troops|soldiers)\s+(deployed|moving|advancing)\b",
            r"\b(infantry|armored|mechanized)\s+(advance|push|crossing)\b",
            r"\bbrigade.{0,20}(deployed|moved|positioned)\b",
            r"\b(idf|irgc|plo|hamas)\s+(forces|troops|units)\s+(enter|deploy|advance)\b",
            r"\bmilitary\s+convoy\b",
            r"\btroop\s+buildup\b",
            r"\breinforcements\s+(sent|deployed|arriving)\b",
        ],
        "score": 0.75,
    },
    {
        "category": EventCategory.naval_event,
        "patterns": [
            r"\bnaval\s+(strike|attack|vessel|blockade|operation)\b",
            r"\bwarship.{0,20}(fired|attacked|hit|sunk)\b",
            r"\bcarrier\s+(group|strike)\b",
            r"\buss\s+\w+\b",
            r"\bhms\s+\w+\b",
            r"\bfrigate|destroyer|corvette|submarine\b",
            r"\bred\s+sea.{0,30}(attack|vessel|drone|missile)\b",
            r"\bpersian\s+gulf.{0,30}(incident|seizure|attack)\b",
            r"\bship.{0,20}(seized|attacked|hit|sunk|drone)\b",
        ],
        "score": 0.80,
    },
    {
        "category": EventCategory.explosion,
        "patterns": [
            r"\b(large|massive|powerful|loud)\s+explosion\b",
            r"\bblast\s+(reported|heard|felt)\b",
            r"\bdetonation\b",
            r"\bboom\s+(heard|reported)\b",
            r"\bexplosion\s+(near|in|at|reported)\b",
        ],
        "score": 0.68,
    },
    {
        "category": EventCategory.casualty_report,
        "patterns": [
            r"\b(\d+)\s+(killed|dead|wounded|injured|casualties)\b",
            r"\bcasualties\s+(reported|confirmed|rising)\b",
            r"\b(civilian|military)\s+(death|casualty|toll)\b",
            r"\binjured.{0,20}\d+\b",
            r"\bmartyrs?\b",
            r"\bfatalities\b",
        ],
        "score": 0.72,
    },
]

# Pre-compile all patterns for performance
_COMPILED_PATTERNS = [
    {
        "category": entry["category"],
        "compiled": [re.compile(p, re.IGNORECASE) for p in entry["patterns"]],
        "score":    entry["score"],
    }
    for entry in CATEGORY_PATTERNS
]

# Keywords that indicate a message is likely conflict-related
CONFLICT_KEYWORDS = re.compile(
    r"\b(attack|strike|bomb|missile|rocket|explosion|casualt|killed|wounded|"
    r"military|troops|forces|army|navy|air\s*force|idf|hamas|hezbollah|"
    r"houthi|irgc|isis|war|conflict|offensive|ceasefire|hostage)\b",
    re.IGNORECASE,
)


def categorize_message(text: str) -> tuple[EventCategory, float]:
    """
    Fast regex-based categorization.
    Returns (EventCategory, confidence_score).
    Returns (unknown, 0.0) if no patterns match.
    Caller should route to LLM if confidence < 0.6.
    """
    if not text:
        return EventCategory.unknown, 0.0

    # Quick pre-filter: must have conflict keywords
    if not CONFLICT_KEYWORDS.search(text):
        return EventCategory.unknown, 0.0

    best_category = EventCategory.unknown
    best_score = 0.0
    best_hit_count = 0

    for entry in _COMPILED_PATTERNS:
        hit_count = sum(1 for pat in entry["compiled"] if pat.search(text))
        if hit_count > 0:
            # Boost score for multiple pattern matches
            score = entry["score"] + (hit_count - 1) * 0.03
            score = min(score, 0.96)
            if score > best_score or (score == best_score and hit_count > best_hit_count):
                best_score    = score
                best_category = entry["category"]
                best_hit_count = hit_count

    return best_category, round(best_score, 3)


def is_conflict_relevant(text: str) -> bool:
    """Quick check if a message is conflict-relevant at all."""
    return bool(CONFLICT_KEYWORDS.search(text)) if text else False


def extract_casualty_count(text: str) -> int | None:
    """Extract the highest casualty number mentioned in a message."""
    pattern = re.compile(r"\b(\d+)\s+(?:killed|dead|wounded|injured|casualties)\b", re.IGNORECASE)
    matches = pattern.findall(text)
    if matches:
        return max(int(m) for m in matches)
    return None


def extract_weapon_mentions(text: str) -> list[str]:
    """Extract weapon system mentions from text."""
    weapon_patterns = [
        r"\b(f-?35|f-?16|su-?35|mig-?\d+)\b",
        r"\b(iron\s+dome|david'?s?\s+sling|arrow\s+[23])\b",
        r"\b(m-?270|himars|grad|bm-?21)\b",
        r"\b(shaheed|shahed|tb-?2|bayraktar)\b",
        r"\b(kornet|atgm|manpads|javelin)\b",
        r"\b(tank|t-?72|t-?90|merkava|abrams)\b",
        r"\b(rpg|ak|kalashnikov)\b",
        r"\b(qassam|katyusha|fadjr)\b",
        r"\b(cruise\s+missile|ballistic\s+missile|hypersonic)\b",
    ]
    found = []
    for pat in weapon_patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        found.extend(matches)
    return list(set(found))


def extract_unit_mentions(text: str) -> list[str]:
    """Extract military unit mentions from text."""
    unit_patterns = [
        r"\b(idf|israel\s+defense\s+forces?)\b",
        r"\b(irgc|islamic\s+revolutionary\s+guard)\b",
        r"\b(hamas(?:'?\s+military\s+wing)?|al-?qassam)\b",
        r"\b(hezbollah|hizb\s*ullah)\b",
        r"\b(houthi|ansarallah)\b",
        r"\b(\d+(?:st|nd|rd|th)\s+(?:brigade|division|battalion|corps))\b",
        r"\b(us\s+(?:army|navy|marines?|air\s+force|centcom))\b",
        r"\b(nato)\b",
        r"\b(plo|fatah|pa\s+security)\b",
        r"\b(isis|isil|daesh)\b",
        r"\b(pmc|wagner)\b",
    ]
    found = []
    for pat in unit_patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            unit = m if isinstance(m, str) else m[0]
            found.append(unit.strip())
    return list(set(found))
