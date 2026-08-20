"""S5-04 — insight replace semantics (Option B, S3-07 Item 3):
crud.replace_insights swaps out one date range's insights entirely, and must
never touch any other range's rows.
"""
from datetime import date, datetime, timezone

from app import crud
from app.models import Insight


def _insight_payload(title: str) -> dict:
    return {"type": "pattern", "title": title, "body": "body text", "severity": "info"}


def test_regenerating_a_range_deletes_only_that_ranges_prior_insights(db_session, test_user):
    august = (date(2026, 8, 1), date(2026, 8, 31))
    july = (date(2026, 7, 1), date(2026, 7, 31))

    crud.replace_insights(
        db_session, test_user.id, *august, [_insight_payload("August v1")], "fake", datetime.now(timezone.utc)
    )
    crud.replace_insights(
        db_session, test_user.id, *july, [_insight_payload("July v1")], "fake", datetime.now(timezone.utc)
    )

    crud.replace_insights(
        db_session,
        test_user.id,
        *august,
        [_insight_payload("August v2 - regenerated")],
        "fake",
        datetime.now(timezone.utc),
    )

    august_insights = crud.list_insights(db_session, test_user.id, *august)
    july_insights = crud.list_insights(db_session, test_user.id, *july)

    assert [i.title for i in august_insights] == ["August v2 - regenerated"]
    assert [i.title for i in july_insights] == ["July v1"]


def test_regenerating_with_zero_insights_leaves_the_range_empty_not_stale(db_session, test_user):
    """A sync that produces zero insights (every category empty, say) must
    correctly leave the range with none — not silently keep the previous
    successful run's stale insights."""
    date_range = (date(2026, 8, 1), date(2026, 8, 31))
    crud.replace_insights(
        db_session, test_user.id, *date_range, [_insight_payload("Stale insight")], "fake", datetime.now(timezone.utc)
    )

    crud.replace_insights(db_session, test_user.id, *date_range, [], "fake", datetime.now(timezone.utc))

    assert crud.list_insights(db_session, test_user.id, *date_range) == []


def test_replace_is_a_single_transaction_row_count_matches_exactly(db_session, test_user):
    date_range = (date(2026, 8, 1), date(2026, 8, 31))
    payload = [_insight_payload("One"), _insight_payload("Two"), _insight_payload("Three")]

    crud.replace_insights(db_session, test_user.id, *date_range, payload, "fake", datetime.now(timezone.utc))

    rows = db_session.query(Insight).filter(Insight.date_from == date_range[0], Insight.date_to == date_range[1]).all()
    assert len(rows) == 3
