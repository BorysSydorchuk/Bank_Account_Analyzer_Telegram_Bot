"""S8-06. Borys's entire operating surface for the closed-beta gate:
grants one real person access by email, nothing more. Run inside a real
running container via ECS Exec (never locally — this needs the real
production DATABASE_URL, and running python ops/x.py directly adds the
script's own directory to sys.path instead of /app, breaking the
`app.*` imports below — run as a module from /app instead):

    aws ecs execute-command --region eu-central-1 --profile kbc-deploy \\
      --cluster kbc-analyzer-cluster --task <task-arn> --container web \\
      --interactive --command \\
      "python -m ops.grant_beta_invite someone@example.com"

Lives in backend/ops/, not backend/scripts/ — scripts/ is dev-only debug
tooling (.dockerignore excludes it entirely from the production image);
this needs to actually exist inside the real production container to be
runnable there at all, so it gets its own directory that Dockerfile.prod
does copy in.

Deliberately a one-shot CLI, not an admin API endpoint — this app has no
admin-role concept at all (CLAUDE.md's multi-user-readiness rules
explicitly avoid building one prematurely), and 10-20 manual grants over
a beta don't justify one. ECS Exec is already this project's established
pattern for every other one-off production operation this sprint
(migrations, DB inspection, the S8-06 pre-check itself).
"""
import sys

from sqlalchemy.exc import IntegrityError

from app.crud import create_beta_invite
from app.db import SessionLocal


def main() -> None:
    """Grant a beta invite to the email passed as the sole CLI argument."""
    if len(sys.argv) != 2:
        print("usage: python -m ops.grant_beta_invite <email>", file=sys.stderr)
        raise SystemExit(1)

    email = sys.argv[1]
    db = SessionLocal()
    try:
        invite = create_beta_invite(db, email)
    except IntegrityError:
        db.rollback()
        print(f"{email.lower()} already has an invite (granted or used) — nothing to do.", file=sys.stderr)
        raise SystemExit(1)
    finally:
        db.close()

    print(f"Granted beta access to {invite.email} (invited_at={invite.invited_at})")


if __name__ == "__main__":
    main()
