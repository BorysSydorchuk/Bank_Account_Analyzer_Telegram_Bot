"""S8-09. One-shot backfill for the real gap S8-09 found: every account
created before this ticket's fix (routers/user_auth.py's two register
paths now seed categories atomically via crud.seed_default_categories)
has zero rows in its own `categories` table, permanently blocking
categorization (analysis_service.categorize_transactions's S5-02 safety
filter rejects every result when the caller's category set is empty).

Run inside a real running container via ECS Exec (never locally — needs
the real production DATABASE_URL, and running python ops/x.py directly
adds the script's own directory to sys.path instead of /app, breaking
the `app.*` imports below — run as a module from /app instead):

    aws ecs execute-command --region eu-central-1 --profile kbc-deploy \\
      --cluster kbc-analyzer-cluster --task <task-arn> --container web \\
      --interactive --command \\
      "python -m ops.backfill_default_categories"

Idempotent by construction: only touches a user with zero existing
categories, so re-running it is always safe — a user seed_default_categories
already covered (this ticket's fix, or a prior run of this same script)
is left untouched, never double-seeded.
"""
from app.crud import list_categories, seed_default_categories
from app.db import SessionLocal
from app.models import User


def main() -> None:
    """Seed default categories for every existing user with none."""
    db = SessionLocal()
    try:
        affected = 0
        for user in db.query(User).order_by(User.created_at).all():
            before = len(list_categories(db, user.id))
            if before > 0:
                print(f"{user.email}: {before} categories already — skipped")
                continue
            seed_default_categories(db, user.id)
            db.commit()
            after = len(list_categories(db, user.id))
            print(f"{user.email}: {before} -> {after} categories")
            affected += 1
        print(f"Done — {affected} account(s) backfilled.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
