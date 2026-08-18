"""S5-04 — manual edit protection invariant. Two functions are under test:
crud.get_uncategorized_transactions (the SELECT that decides what the
categorization agent even sees) and crud.update_transaction_categories (the
UPDATE that writes its results back) — both have to independently respect
manually_edited, because a row can become manually_edited in the gap between
the two (see the race-condition test below).
"""
from app import crud


def test_manually_edited_row_is_excluded_from_the_categorization_query(db_session, transaction_factory):
    edited = transaction_factory(category=None, manually_edited=True)
    untouched = transaction_factory(category=None, manually_edited=False)
    db_session.add_all([edited, untouched])
    db_session.flush()

    uncategorized = crud.get_uncategorized_transactions(db_session)

    ids = {t.id for t in uncategorized}
    assert edited.id not in ids
    assert untouched.id in ids


def test_manually_edited_row_excluded_even_when_category_is_null_S3_05(db_session, transaction_factory):
    """The subtle case (verified live in S3-05): a user can manually CLEAR a
    category, leaving it NULL — that NULL must still read as "a human already
    decided this," not "nobody has looked at this yet." If the query only
    checked category IS NULL, a cleared row would look identical to a never-
    categorized one and get silently re-guessed on the next run.
    """
    cleared_by_hand = transaction_factory(category=None, manually_edited=True)
    db_session.add(cleared_by_hand)
    db_session.flush()

    uncategorized = crud.get_uncategorized_transactions(db_session)

    assert cleared_by_hand.id not in {t.id for t in uncategorized}


def test_update_never_overwrites_an_already_categorized_row(db_session, transaction_factory):
    already_categorized = transaction_factory(category="Groceries", manually_edited=False)
    db_session.add(already_categorized)
    db_session.flush()

    crud.update_transaction_categories(
        db_session, [{"id": str(already_categorized.id), "category": "Other", "subcategory": None}]
    )

    db_session.refresh(already_categorized)
    assert already_categorized.category == "Groceries"


def test_race_condition_row_edited_between_select_and_update_stays_protected(db_session, transaction_factory):
    """The specific protection found during interview-prep study: the SELECT
    (get_uncategorized_transactions) and the UPDATE (update_transaction_categories)
    are two separate statements, with the LLM call in between — long enough
    for a real user to edit the row by hand in the meantime. If the UPDATE
    trusted the SELECT's result set instead of re-checking manually_edited in
    its own WHERE clause, that edit would be silently overwritten the moment
    the categorization batch came back.

    Simulated here without actually racing threads: SELECT first (row is
    eligible), then a manual edit happens (simulating the user acting during
    the LLM round-trip), then the UPDATE runs with the id the SELECT saw —
    exactly the interleaving a real race would produce.

    The simulated edit clears the category to NULL (a manual "clear," same
    as S3-05) rather than setting it to some other category name. That's
    deliberate (review finding): update_transaction_categories' WHERE
    clause checks BOTH `category IS NULL` and `manually_edited IS FALSE` —
    if the simulated edit set a non-null category, the UPDATE would be
    blocked by the category-not-null condition alone, and the test would
    pass even if the manually_edited re-check were deleted entirely. Only
    an edit that leaves category NULL isolates that manually_edited is
    actually the thing doing the protecting here.
    """
    row = transaction_factory(category=None, manually_edited=False, description="Ambiguous Merchant")
    db_session.add(row)
    db_session.flush()

    eligible_before_the_race = crud.get_uncategorized_transactions(db_session)
    assert row.id in {t.id for t in eligible_before_the_race}

    crud.update_transaction(db_session, row.id, {"category": None})

    crud.update_transaction_categories(
        db_session, [{"id": str(row.id), "category": "Other", "subcategory": "Shopping"}]
    )

    db_session.refresh(row)
    assert row.category is None
    assert row.manually_edited is True
