"""One-off script: grants (or revokes) admin status for one user, by username.

`is_admin` exists for exactly one reason -- letting the project owner bypass the analysis
quota for testing. There's no self-serve admin UI on purpose; this script is the only way to
set it, run directly against the DB by whoever operates the app.

Defaults to a dry run (reports the user's current status, changes nothing). Pass --execute
to actually apply the change.

Usage:
    python -m scripts.grant_admin --username alice                 # dry run
    python -m scripts.grant_admin --username alice --execute       # grant
    python -m scripts.grant_admin --username alice --revoke --execute  # revoke
"""

import argparse
import logging

from app.db.session import SessionLocal
from app.models import User

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="Username of the account to modify")
    parser.add_argument("--revoke", action="store_true", help="Revoke admin instead of granting it")
    parser.add_argument("--execute", action="store_true", help="Actually apply the change (default: dry run)")
    args = parser.parse_args()

    target_value = not args.revoke

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        if user is None:
            logger.error("No user found with username '%s'", args.username)
            return

        action = "grant" if target_value else "revoke"
        if user.is_admin == target_value:
            logger.info("'%s' already has is_admin=%s -- nothing to do.", args.username, target_value)
            return

        if not args.execute:
            logger.info(
                "DRY RUN -- would %s admin for '%s' (is_admin: %s -> %s). Pass --execute to apply.",
                action,
                args.username,
                user.is_admin,
                target_value,
            )
            return

        user.is_admin = target_value
        db.commit()
        logger.info("Done -- '%s' is_admin is now %s.", args.username, target_value)
    finally:
        db.close()


if __name__ == "__main__":
    main()
