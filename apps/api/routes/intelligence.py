"""Commercial Intelligence — internal protected read surfaces.

Phase B endpoints:
- GET /internal/intelligence/loss-analysis
- GET /internal/intelligence/score-effectiveness
- GET /internal/intelligence/cohorts

Stage progression metrics (contacted_or_beyond, qualified_or_beyond) are derived
from lead_outcome_history as "ever reached stage".

Current/latest-outcome metrics (won, lost, bad_fit, no_answer) are derived from
the current snapshot in lead_outcomes.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from apps.api.auth import require_api_key
from apps.api.db import get_db
from apps.api.schemas import (
    CohortItem,
    CohortsResponse,
    LossAnalysisBySource,
    LossAnalysisResponse,
    LossReasonCounts,
    ScoreEffectivenessBucket,
    ScoreEffectivenessResponse,
)

router = APIRouter(
    prefix="/internal/intelligence",
    dependencies=[Depends(require_api_key)],
    tags=["intelligence"],
)

# Stages for history-derived metrics
_CONTACTED_OR_BEYOND = {"contacted", "qualified", "won", "lost", "bad_fit", "no_answer"}
_QUALIFIED_OR_BEYOND = {"qualified", "won", "lost", "bad_fit"}

_LOSS_REASON_KEYS = ("price", "timing", "competitor", "no_need", "no_response", "other")

_SCORE_BUCKETS = [
    ("0-30", 0, 30),
    ("31-50", 31, 50),
    ("51-70", 51, 70),
    ("71-100", 71, 100),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _top_reason(counts: dict[str, int]) -> str | None:
    """Return the loss_reason key with the highest count, excluding 'unspecified'. None if all zero."""
    best_key = None
    best_val = 0
    for k in _LOSS_REASON_KEYS:
        if counts.get(k, 0) > best_val:
            best_val = counts[k]
            best_key = k
    return best_key


def _reason_counts(rows: list) -> dict[str, int]:
    """Count loss_reason values from a list of rows with 'loss_reason' field."""
    counts = {k: 0 for k in _LOSS_REASON_KEYS}
    counts["unspecified"] = 0
    for r in rows:
        lr = r["loss_reason"]
        if lr and lr in counts:
            counts[lr] += 1
        else:
            counts["unspecified"] += 1
    return counts


# ---------------------------------------------------------------------------
# GET /internal/intelligence/loss-analysis
# ---------------------------------------------------------------------------


@router.get("/loss-analysis", response_model=LossAnalysisResponse)
def get_loss_analysis(
    source: str | None = Query(None, description="Exact source filter"),
) -> LossAnalysisResponse:
    """Distribution of loss reasons, optionally filtered by source."""
    db = get_db()

    where = "lo.outcome = 'lost'"
    params: list = []
    if source:
        where += " AND l.source = ?"
        params.append(source)

    rows = db.execute(
        f"SELECT l.source, lo.loss_reason "
        f"FROM lead_outcomes lo JOIN leads l ON lo.lead_id = l.id "
        f"WHERE {where}",
        params,
    ).fetchall()

    # Global counts
    global_counts = _reason_counts(rows)
    total_lost = len(rows)

    # By source
    by_src: dict[str, list] = {}
    for r in rows:
        by_src.setdefault(r["source"], []).append(r)

    by_source_items = []
    for src in sorted(by_src, key=lambda s: -len(by_src[s])):
        src_rows = by_src[src]
        src_counts = _reason_counts(src_rows)
        by_source_items.append(
            LossAnalysisBySource(
                source=src,
                total_lost=len(src_rows),
                top_reason=_top_reason(src_counts),
                reasons=LossReasonCounts(**src_counts),
            )
        )

    return LossAnalysisResponse(
        generated_at=_now_iso(),
        source_filter=source,
        total_lost=total_lost,
        by_reason=LossReasonCounts(**global_counts),
        top_reason=_top_reason(global_counts),
        by_source=by_source_items,
    )


# ---------------------------------------------------------------------------
# GET /internal/intelligence/score-effectiveness
# ---------------------------------------------------------------------------


def _history_stage_counts(lead_ids: set[int], db) -> tuple[dict[int, bool], dict[int, bool]]:
    """Return dicts mapping lead_id -> True for contacted_or_beyond / qualified_or_beyond.

    Derived from lead_outcome_history (ever reached stage), NOT current snapshot.
    """
    if not lead_ids:
        return {}, {}

    placeholders = ",".join("?" * len(lead_ids))
    rows = db.execute(
        f"SELECT DISTINCT lead_id, outcome FROM lead_outcome_history "
        f"WHERE lead_id IN ({placeholders})",
        list(lead_ids),
    ).fetchall()

    contacted: dict[int, bool] = {}
    qualified: dict[int, bool] = {}
    for r in rows:
        lid = r["lead_id"]
        outcome = r["outcome"]
        if outcome in _CONTACTED_OR_BEYOND:
            contacted[lid] = True
        if outcome in _QUALIFIED_OR_BEYOND:
            qualified[lid] = True

    return contacted, qualified


@router.get("/score-effectiveness", response_model=ScoreEffectivenessResponse)
def get_score_effectiveness(
    source: str | None = Query(None, description="Exact source filter"),
) -> ScoreEffectivenessResponse:
    """Score vs outcome correlation by score buckets."""
    db = get_db()

    where = "1=1"
    params: list = []
    if source:
        where += " AND l.source = ?"
        params.append(source)

    # Leads with outcomes (current snapshot for won/lost/bad_fit/no_answer)
    rows = db.execute(
        f"SELECT l.id, l.score, lo.outcome "
        f"FROM leads l JOIN lead_outcomes lo ON l.id = lo.lead_id "
        f"WHERE {where}",
        params,
    ).fetchall()

    # Collect all lead_ids for history lookup
    all_lead_ids = {r["id"] for r in rows}
    contacted_map, qualified_map = _history_stage_counts(all_lead_ids, db)

    # Build buckets
    buckets = []
    for label, lo, hi in _SCORE_BUCKETS:
        bucket_rows = [r for r in rows if lo <= r["score"] <= hi]
        total = len(bucket_rows)

        # Current snapshot counts
        won = sum(1 for r in bucket_rows if r["outcome"] == "won")
        lost = sum(1 for r in bucket_rows if r["outcome"] == "lost")
        bad_fit = sum(1 for r in bucket_rows if r["outcome"] == "bad_fit")
        no_answer = sum(1 for r in bucket_rows if r["outcome"] == "no_answer")

        # History-derived stage counts
        c_or_b = sum(1 for r in bucket_rows if contacted_map.get(r["id"], False))
        q_or_b = sum(1 for r in bucket_rows if qualified_map.get(r["id"], False))

        terminal = won + lost + bad_fit

        buckets.append(
            ScoreEffectivenessBucket(
                range=label,
                total=total,
                contacted_or_beyond=c_or_b,
                qualified_or_beyond=q_or_b,
                won=won,
                lost=lost,
                bad_fit=bad_fit,
                no_answer=no_answer,
                contact_rate=round(c_or_b / total, 2) if total else 0.0,
                qualification_rate=round(q_or_b / total, 2) if total else 0.0,
                win_rate_on_terminal=round(won / terminal, 2) if terminal else 0.0,
            )
        )

    total_with_outcomes = len(rows)

    # Scoring accuracy signal
    if total_with_outcomes < 10:
        signal = "insufficient_data"
    else:
        high_bucket = buckets[3]  # 71-100
        low_bucket = buckets[0]   # 0-30
        if high_bucket.win_rate_on_terminal > low_bucket.win_rate_on_terminal:
            signal = "reliable"
        else:
            signal = "weak"

    return ScoreEffectivenessResponse(
        generated_at=_now_iso(),
        source_filter=source,
        total_with_outcomes=total_with_outcomes,
        buckets=buckets,
        scoring_accuracy_signal=signal,
    )


# ---------------------------------------------------------------------------
# GET /internal/intelligence/cohorts
# ---------------------------------------------------------------------------


@router.get("/cohorts", response_model=CohortsResponse)
def get_cohorts(
    months: int = Query(3, ge=1, le=12, description="Number of months to include"),
    source: str | None = Query(None, description="Exact source filter"),
) -> CohortsResponse:
    """Monthly cohort analysis based on lead creation month."""
    db = get_db()

    # Determine the month range: from (current_month - months + 1) to current_month
    now = datetime.now(timezone.utc)
    # Build list of month labels
    month_labels = []
    for i in range(months - 1, -1, -1):
        # Go back i months from now
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_labels.append(f"{y:04d}-{m:02d}")

    where = "1=1"
    params: list = []
    if source:
        where += " AND l.source = ?"
        params.append(source)

    # All leads created in the date range
    first_month = month_labels[0]
    leads_where = f"{where} AND strftime('%Y-%m', l.created_at) >= ?"
    params.append(first_month)

    rows = db.execute(
        f"SELECT l.id, l.score, strftime('%Y-%m', l.created_at) as month "
        f"FROM leads l WHERE {leads_where}",
        params,
    ).fetchall()

    # Current outcomes for these leads
    lead_ids = [r["id"] for r in rows]
    outcome_map: dict[int, str] = {}
    if lead_ids:
        placeholders = ",".join("?" * len(lead_ids))
        outcome_rows = db.execute(
            f"SELECT lead_id, outcome FROM lead_outcomes WHERE lead_id IN ({placeholders})",
            lead_ids,
        ).fetchall()
        outcome_map = {r["lead_id"]: r["outcome"] for r in outcome_rows}

    # History-derived stage counts
    contacted_map, qualified_map = _history_stage_counts(set(lead_ids), db)

    # Group leads by month
    by_month: dict[str, list] = {m: [] for m in month_labels}
    for r in rows:
        m = r["month"]
        if m in by_month:
            by_month[m].append(r)

    cohort_items = []
    for month_label in month_labels:
        month_rows = by_month[month_label]
        leads_created = len(month_rows)

        leads_with_outcome = [r for r in month_rows if r["id"] in outcome_map]
        with_outcomes = len(leads_with_outcome)

        # Current snapshot counts
        won = sum(1 for r in leads_with_outcome if outcome_map[r["id"]] == "won")
        lost = sum(1 for r in leads_with_outcome if outcome_map[r["id"]] == "lost")
        bad_fit = sum(1 for r in leads_with_outcome if outcome_map[r["id"]] == "bad_fit")
        no_answer = sum(1 for r in leads_with_outcome if outcome_map[r["id"]] == "no_answer")

        # History-derived stage counts
        c_or_b = sum(1 for r in leads_with_outcome if contacted_map.get(r["id"], False))
        q_or_b = sum(1 for r in leads_with_outcome if qualified_map.get(r["id"], False))

        # Avg score (all leads in cohort, not just those with outcomes)
        avg_score = round(sum(r["score"] for r in month_rows) / leads_created, 1) if leads_created else 0.0

        terminal = won + lost + bad_fit

        cohort_items.append(
            CohortItem(
                month=month_label,
                leads_created=leads_created,
                with_outcomes=with_outcomes,
                contacted_or_beyond=c_or_b,
                qualified_or_beyond=q_or_b,
                won=won,
                lost=lost,
                bad_fit=bad_fit,
                no_answer=no_answer,
                avg_score=avg_score,
                contact_rate=round(c_or_b / with_outcomes, 2) if with_outcomes else 0.0,
                qualification_rate=round(q_or_b / with_outcomes, 2) if with_outcomes else 0.0,
                win_rate_on_terminal=round(won / terminal, 2) if terminal else 0.0,
            )
        )

    return CohortsResponse(
        generated_at=_now_iso(),
        source_filter=source,
        months_requested=months,
        cohorts=cohort_items,
    )
