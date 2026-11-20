"""SEED Autonomous Semantic Memory Engine.

Decides *what* to remember from normal conversation, classifies it, stores it
through the governed memory store, recalls only relevant items, resolves
conflicts when facts change, and records an auditable history of every
memory operation.

Design goals
------------
1. Formation   - extract durable, useful knowledge from ordinary dialogue
                 instead of storing every message indiscriminately.
2. Classify    - separate durable facts, preferences, project decisions,
                 temporary context and task history.
3. Retrieval   - relevance-scored recall so that irrelevant memories are
                 never injected into a prompt.
4. Update      - latest value wins for the same logical subject, and the
                 superseded value is preserved in the audit history.
5. Observability - every create / update / retrieve decision is logged with
                   an explicit reason in the ``memory_events`` table.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from memory import store


# ---------------------------------------------------------------------------
# Memory taxonomy
# ---------------------------------------------------------------------------

# Mapping between the semantic categories used by this engine and the
# persistent memory types accepted by ``memory.store.save_memory``.
CATEGORY_DURABLE_FACT = "durable_fact"
CATEGORY_PREFERENCE = "preference"
CATEGORY_PROJECT_DECISION = "project_decision"
CATEGORY_TEMPORARY = "temporary_context"
CATEGORY_TASK_HISTORY = "task_history"

CATEGORY_TO_STORE_TYPE = {
    CATEGORY_DURABLE_FACT: "durable_knowledge",
    CATEGORY_PREFERENCE: "user_preference",
    CATEGORY_PROJECT_DECISION: "project_decision",
    CATEGORY_TEMPORARY: "temporary_context",
    CATEGORY_TASK_HISTORY: "task_history",
}

STORE_TYPE_TO_CATEGORY = {v: k for k, v in CATEGORY_TO_STORE_TYPE.items()}


# Arabic + English linguistic markers ----------------------------------------

_FACT_MARKERS = (
    # Arabic statement-of-fact verbs / copula
    "هو ", "هي ", "هما ", "هم ", "تساوي", "يساوي", "يعني", "تعني",
    "اسمه", "اسمها", "يسمى", "تسمى", "الهوية", "هوية", "الكود", "كود",
    # English
    " is ", " are ", " means ", " refers to ", " stands for ", " equals ",
    "identity", "codename", "code name", "named", "called",
)

_PREFERENCE_MARKERS = (
    "أفضل", "أحب", "أكره", "أريد", "أفضل أن", "يفضل", "تفضل",
    " i like ", " i love ", " i hate ", " i prefer ", " i want ",
    " prefer ", "favourite", "favorite", "always use", "never use",
)

_DECISION_MARKERS = (
    "قررنا", "اتفقنا", "اخترنا", "نقرر", "القرار", "تقّرر",
    " we decided ", " we chose ", " decided to ", " decision is ",
    " we agreed ", " the plan is ", " final choice",
)

_TEMPORARY_MARKERS = (
    "مؤقتا", "مؤقت", "لحظيا", "الآن فقط", "هذه المرة فقط",
    " temporarily ", " for now ", " just this once ", " for the moment ",
)

# Question forms - used to suppress memory formation on pure questions.
_QUESTION_MARKERS_EN = (
    "what", "who", "when", "where", "why", "how", "which", "?"
)
_QUESTION_MARKERS_AR = (
    "ما ", "ماذا", "من ", "متى", "أين", "لماذا", "كيف", "هل ", "؟", "ايه", "إيه"
)

# ---------------------------------------------------------------------------
# Language-independent semantic identity
# ---------------------------------------------------------------------------
#
# The crucial correctness property: the *same* logical fact expressed in
# Arabic and in English must resolve to the *same* memory key, so that an
# update in one language supersedes the value stored in the other, and a
# recall query in either language finds it.
#
# We achieve this with a small bilingual concept lexicon. Each canonical
# concept (e.g. ``project_codename``) has a set of surface terms across
# languages. When a fact statement mentions any surface term we key the fact
# on the canonical concept instead of on the raw sentence.

_CONCEPT_LEXICON: Dict[str, Tuple[str, ...]] = {
    "project_codename": (
        # English
        "codename", "code name", "project code", "project name",
        "project identity", "project id", "identity", "code",
        # Arabic
        "كود المشروع", "كود", "هوية المشروع", "هوية", "اسم المشروع",
        "اسم", "رقم المشروع", "رمز المشروع", "معرف المشروع",
    ),
    "project_status": (
        "project status", "status", "حالة المشروع", "الحالة",
    ),
    "project_owner": (
        "project owner", "owner", "مالك المشروع", "المالك",
    ),
    "user_name": (
        "my name", "user name", "username", "اسمي", "اسم المستخدم",
    ),
}

# Reverse index: surface term -> canonical concept (longest first).
_CONCEPT_SURFACES: List[Tuple[str, str]] = sorted(
    (
        (surface, concept)
        for concept, surfaces in _CONCEPT_LEXICON.items()
        for surface in surfaces
    ),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

# Value-extraction patterns, ordered by specificity. Group 1 is the value.
_VALUE_PATTERNS = [
    # Arabic: "...(هو|هي|أصبح|اصبح|أصبحت|تساوي|يساوي|:|=) <value>"
    r"(?:هو|هي|أصبح|اصبح|أصبحت|اصبحت|تساوي|يساوي|يعني|:|=)\s*"
    r"[\"'«]?\s*([A-Za-z0-9\u0600-\u06FF][A-Za-z0-9\u0600-\u06FF\-_\.]{1,60})",
    # English: "is / equals / now / : / = <value>"
    r"(?:is|equals|refers to|stands for|:|now)\s+"
    r"[\"'«]?\s*([A-Za-z0-9][A-Za-z0-9\-_\.]{1,60})",
    # Any ALL-CAPS-ish identifier token: ORBIT-731, PROJECT-ALPHA-912
    r"([A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)+)",
]

# Subject patterns retained as a fallback when no concept is recognised.
_SUBJECT_PATTERNS = [
    # Arabic: "هوية مشروعنا ... هي <value>" / "كود المشروع هو <value>"
    r"(?:هوية|كود|اسم|رقم|codename|code name)\s*(?:ال)?(?:مشروع|مشروعنا|مشروعى|platform|product)?[^\n]{0,30}?(?:هو|هي|تساوي|يساوي|:|=)\s*[\"']?([^\n\"'.،]{2,80})",
    # English: "our project identity is <value>"
    r"(?:our|the|my)\s+(?:project|team|product|platform)?\s*(?:identity|codename|code name|name)\s+(?:is|equals)\s*[\"']?([^\n\"'.،]{2,80})",
    # Generic "<subject> is <value>"
    r"[\"']?([A-Z][A-Z0-9][A-Z0-9\-_]{2,40})[\"']?",
]


def _detect_concept(text: str) -> Optional[str]:
    """Return the canonical concept named in ``text``, if any.

    Uses the bilingual lexicon; longer surface terms win so that
    "project codename" is preferred over "code".
    """
    normalised = _normalise(text)
    padded = f" {normalised} "
    for surface, concept in _CONCEPT_SURFACES:
        surface_norm = _normalise(surface)
        if not surface_norm:
            continue
        # Word-boundary match for latin terms, substring for Arabic.
        if re.fullmatch(r"[a-z0-9 ]+", surface_norm):
            if re.search(rf"\b{re.escape(surface_norm)}\b", padded):
                return concept
        elif surface_norm in padded:
            return concept
    return None


def _extract_fact_value(text: str) -> str:
    """Extract the asserted value of a fact statement (best effort)."""
    for pattern in _VALUE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip().strip("\"'«».,،")
        if not value:
            continue
        # Skip time/ordinal adjectives that are not fact values.
        if value.lower() in {
            "المشروع", "project", "the", "now", "الآن", "حاليا", "حالياً",
        }:
            continue
        return value
    # Last resort: any ALL-CAPS identifier token such as ORBIT-731.
    token = re.search(r"\b([A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)+)\b", text)
    if token:
        return token.group(1)
    return ""


@dataclass(frozen=True)
class MemoryCandidate:
    """A piece of knowledge worth remembering, extracted from conversation."""

    category: str
    memory_key: str
    content: str
    confidence: float
    reason: str
    approx_value: str = ""

    @property
    def store_type(self) -> str:
        return CATEGORY_TO_STORE_TYPE[self.category]


@dataclass
class RecallResult:
    """A retrieved memory with an explicit relevance score and trace."""

    memory_type: str
    memory_key: str
    content: str
    score: float
    matched_terms: Tuple[str, ...] = field(default_factory=tuple)

    def as_context(self) -> Dict[str, Any]:
        return {
            "type": self.memory_type,
            "key": self.memory_key,
            "content": self.content,
        }


def _normalise(text: str) -> str:
    """Lower-cased, diacritic-stripped, whitespace-collapsed text."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    # Arabic tatweel / punctuation normalisation
    stripped = stripped.replace("\u0640", "")
    stripped = re.sub(r"[^\w\s\u0600-\u06FF-]", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _is_question(text: str) -> bool:
    lowered = f" {text.strip().lower()} "
    if "?" in text or "؟" in text:
        # A question mark does not preclude a statement, but combined with a
        # leading interrogative it usually means no durable fact is asserted.
        if any(m in lowered for m in _QUESTION_MARKERS_AR) or any(
            lowered.strip().startswith(m) for m in _QUESTION_MARKERS_EN
        ):
            return True
    for marker in _QUESTION_MARKERS_AR:
        if text.strip().startswith(marker.strip()):
            return True
    for marker in _QUESTION_MARKERS_EN:
        if marker == "?":
            continue
        if lowered.strip().startswith(marker):
            return True
    return False


def _contains_any(text: str, markers: Sequence[str]) -> Optional[str]:
    lowered = f" {text.lower()} "
    for marker in markers:
        if marker in lowered:
            return marker
    return None


def _slug(text: str, limit: int = 48) -> str:
    cleaned = _normalise(text).replace(" ", "_")
    cleaned = re.sub(r"[^a-z0-9_\u0600-\u06FF-]", "", cleaned)
    return cleaned[:limit] or "memory"


class SemanticMemoryEngine:
    """Autonomous memory formation, recall, and audit for SEED."""

    # -- formation ---------------------------------------------------------

    @staticmethod
    def extract_candidates(prompt: str) -> List[MemoryCandidate]:
        """Inspect a user utterance and return knowledge worth remembering.

        Only statements survive; pure questions never form memory. Each
        candidate carries a category, a stable key, the extracted content and
        the reason it was selected (for the audit trail).
        """
        if not prompt or not prompt.strip():
            return []

        text = prompt.strip()
        candidates: List[MemoryCandidate] = []

        if _is_question(text):
            return []

        # --- temporary context -------------------------------------------
        temp_marker = _contains_any(text, _TEMPORARY_MARKERS)
        if temp_marker:
            candidates.append(
                MemoryCandidate(
                    category=CATEGORY_TEMPORARY,
                    memory_key="temporary_" + _slug(text),
                    content=text[:500],
                    confidence=0.6,
                    reason=f"temporary marker '{temp_marker.strip()}'",
                )
            )
            # Temporary context is exclusive: do not also mint a durable fact.
            return candidates

        # --- preference ---------------------------------------------------
        pref_marker = _contains_any(text, _PREFERENCE_MARKERS)
        if pref_marker:
            candidates.append(
                MemoryCandidate(
                    category=CATEGORY_PREFERENCE,
                    memory_key="preference_" + _slug(text),
                    content=text[:500],
                    confidence=0.75,
                    reason=f"preference marker '{pref_marker.strip()}'",
                )
            )

        # --- project decision ---------------------------------------------
        decision_marker = _contains_any(text, _DECISION_MARKERS)
        if decision_marker:
            candidates.append(
                MemoryCandidate(
                    category=CATEGORY_PROJECT_DECISION,
                    memory_key="decision_" + _slug(text),
                    content=text[:500],
                    confidence=0.8,
                    reason=f"decision marker '{decision_marker.strip()}'",
                )
            )

        # --- durable fact -------------------------------------------------
        fact_marker = _contains_any(text, _FACT_MARKERS)
        if fact_marker:
            concept = _detect_concept(text)
            value = _extract_fact_value(text)
            if concept:
                # Language-independent key: same fact in Arabic or English
                # resolves to the same key, so updates supersede correctly
                # and recall works across languages.
                key = f"fact:{concept}"
                confidence = 0.9 if value else 0.8
                reason = f"canonical concept '{concept}'"
            else:
                subject, fallback_value = SemanticMemoryEngine._extract_subject_value(text)
                key = "fact_" + (_slug(subject) if subject else _slug(text))
                value = value or fallback_value
                confidence = 0.85
                reason = f"fact marker '{fact_marker.strip()}'"
            # Store a language-neutral canonical content line so cross-language
            # recall does not depend on which language first recorded the fact.
            content = (
                f"{concept} = {value}" if concept and value else text[:500]
            )
            candidates.append(
                MemoryCandidate(
                    category=CATEGORY_DURABLE_FACT,
                    memory_key=key,
                    content=content,
                    confidence=confidence,
                    reason=reason,
                    approx_value=value,
                )
            )

        # De-duplicate by (category, key) keeping highest confidence.
        deduped: Dict[Tuple[str, str], MemoryCandidate] = {}
        for cand in candidates:
            ident = (cand.category, cand.memory_key)
            existing = deduped.get(ident)
            if existing is None or cand.confidence > existing.confidence:
                deduped[ident] = cand
        return list(deduped.values())

    @staticmethod
    def _extract_subject_value(text: str) -> Tuple[str, str]:
        """Best-effort (subject, value) split for a fact statement."""
        for pattern in _SUBJECT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            if not value:
                continue
            start = max(0, match.start() - 60)
            subject_region = text[start:match.start()].strip()
            subject_terms = _normalise(subject_region).split()[-4:]
            subject = " ".join(subject_terms) or _normalise(value)
            return subject, value
        return "", ""

    # -- persistence -------------------------------------------------------

    @staticmethod
    def form_memory(candidate: MemoryCandidate, project_id: str = "",
                    session_id: str = "", task_id: Optional[int] = None) -> Dict[str, Any]:
        """Persist a candidate, resolving conflicts and auditing the decision."""
        existing = store.get_memory(
            candidate.store_type, candidate.memory_key, project_id=project_id
        )

        # Confidence gate: low-confidence inferences are not persisted durably.
        if candidate.confidence < 0.6:
            SemanticMemoryEngine._audit(
                candidate, project_id, session_id, task_id,
                operation="skipped",
            )
            return {
                "operation": "skipped",
                "memory_key": candidate.memory_key,
                "category": candidate.category,
                "reason": "below confidence threshold",
            }

        operation = "updated" if existing is not None else "created"
        if existing is not None and existing["content"] == candidate.content:
            operation = "unchanged"

        store.save_memory(
            memory_type=candidate.store_type,
            memory_key=candidate.memory_key,
            content=candidate.content,
            project_id=project_id,
            approved=(candidate.category != CATEGORY_PREFERENCE),
            source_task_id=task_id,
        )

        SemanticMemoryEngine._audit(
            candidate, project_id, session_id, task_id, operation=operation
        )
        return {
            "operation": operation,
            "memory_key": candidate.memory_key,
            "memory_type": candidate.store_type,
            "category": candidate.category,
            "reason": candidate.reason,
            "previous_content": existing["content"] if existing else None,
        }

    @staticmethod
    def remember_from_turn(prompt: str, project_id: str = "",
                           session_id: str = "", task_id: Optional[int] = None
                           ) -> List[Dict[str, Any]]:
        """Full formation step for one conversational turn."""
        results: List[Dict[str, Any]] = []
        for candidate in SemanticMemoryEngine.extract_candidates(prompt):
            try:
                results.append(
                    SemanticMemoryEngine.form_memory(
                        candidate, project_id=project_id,
                        session_id=session_id, task_id=task_id,
                    )
                )
            except Exception as error:  # noqa: BLE001 - never break a turn
                results.append({
                    "operation": "error",
                    "memory_key": candidate.memory_key,
                    "category": candidate.category,
                    "reason": f"{type(error).__name__}: {error}",
                })
        return results

    # -- recall ------------------------------------------------------------

    @staticmethod
    def recall(prompt: str, project_id: str = "", limit: int = 6,
               min_score: float = 0.15) -> List[RecallResult]:
        """Relevance-scored memory recall.

        Unlike a naive keyword dump this scores each stored memory against the
        query, drops anything below ``min_score`` and de-duplicates by key so
        only genuinely relevant context reaches the model.
        """
        if not prompt or not prompt.strip():
            return []

        terms = [t for t in _normalise(prompt).split() if len(t) > 2][:10]
        if not terms:
            return []

        # Detect the canonical concept in the query (cross-language).
        query_concept = _detect_concept(prompt)

        # Broad candidate pull, then re-rank locally.
        raw = store.search_memory(prompt, project_id=project_id, limit=max(limit * 4, 24))
        if not raw:
            # Fallback for cross-language queries where LIKE can't match
            # stored content in the other language. Use list_memories and
            # filter by concept matching.
            if query_concept:
                all_rows = store.list_memories(project_id=project_id, limit=200)
                raw = [
                    r for r in all_rows
                    if f"fact:{query_concept}" in r["memory_key"]
                ]

        # Arabic-aware key content signals and expanded terms.
        # If the query maps to a canonical concept, expand with all surface terms
        # so that a query containing e.g. "codename" also matches stored "كود" / "هوية".
        # Also add the concept name itself so it matches `fact:project_codename`.
        expanded = set(terms)
        if query_concept:
            concept_norm = _normalise(query_concept)
            expanded.add(concept_norm)
            expanded.update(_normalise(s) for s in _CONCEPT_LEXICON.get(query_concept, ()))

        for term in terms:
            for concept, surfaces in _CONCEPT_LEXICON.items():
                for surface in surfaces:
                    if _normalise(surface) == term:
                        expanded.update(_normalise(s) for s in surfaces)
                        break

        if query_concept:
            expanded.update(_normalise(s) for s in _CONCEPT_LEXICON.get(query_concept, ()))

        scored: List[RecallResult] = []
        if not raw:
            return []
        for row in raw:
            haystack = _normalise(f"{row['memory_key']} {row['content']}")
            matched = sorted({t for t in expanded if t and t in haystack})
            if not matched:
                continue
            # Weighted score: term overlap + key-specific bonus.
            overlap = len(matched) / max(len(expanded), 1)
            key_bonus = 0.25 if any(t in _normalise(row["memory_key"]) for t in matched) else 0.0
            # Strong bonus if the stored key matches the query's concept.
            concept_bonus = 0.5 if query_concept and f"fact:{query_concept}" in row["memory_key"] else 0.0
            approved_bonus = 0.1 if row.get("approved") else 0.0
            score = min(1.0, overlap * 0.8 + key_bonus + concept_bonus + approved_bonus)
            if score < min_score:
                continue
            scored.append(
                RecallResult(
                    memory_type=row["memory_type"],
                    memory_key=row["memory_key"],
                    content=row["content"],
                    score=round(score, 3),
                    matched_terms=tuple(matched),
                )
            )

        scored.sort(key=lambda r: r.score, reverse=True)

        # De-duplicate: keep the strongest hit per memory_key.
        seen: set[str] = set()
        unique: List[RecallResult] = []
        for result in scored:
            if result.memory_key in seen:
                continue
            seen.add(result.memory_key)
            unique.append(result)
            if len(unique) >= limit:
                break
        return unique

    # -- audit -------------------------------------------------------------

    @staticmethod
    def _audit(candidate: MemoryCandidate, project_id: str, session_id: str,
               task_id: Optional[int], operation: str) -> None:
        try:
            store.record_memory_event(
                memory_key=candidate.memory_key,
                memory_type=candidate.store_type,
                content=candidate.content,
                operation=operation,
                project_id=project_id,
                session_id=session_id,
                task_id=task_id,
            )
        except Exception:
            pass

    @staticmethod
    def record_recall(results: Sequence[RecallResult], prompt: str,
                      project_id: str = "", session_id: str = "",
                      task_id: Optional[int] = None) -> None:
        """Audit which memories were surfaced and why."""
        for result in results:
            try:
                store.record_memory_event(
                    memory_key=result.memory_key,
                    memory_type=result.memory_type,
                    content=result.content,
                    operation="retrieved",
                    project_id=project_id,
                    session_id=session_id,
                    task_id=task_id,
                )
            except Exception:
                pass

    @staticmethod
    def history(project_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """Return the auditable history of memory operations."""
        return store.list_memory_events(project_id=project_id, limit=limit)
