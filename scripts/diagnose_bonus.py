#!/usr/bin/env python
"""Read-only Diagnose für oa6n: Warum fehlt eine Bonus-Challenge im Selektor?

Macht ausschließlich SELECT-Abfragen (ändert NICHTS) und zeigt:
  1. an welcher Challenge jede Bonus-Challenge hängt,
  2. die Teilnahmen des angegebenen Users mit Status,
  3. welche Challenges die Bonus-Übersicht für ihn im Selektor zeigen würde
     (= Quelle _user_accepted_challenges: nur status='accepted').

Aufruf (im Container):
    docker compose exec web python scripts/diagnose_bonus.py DEINE_EMAIL
"""
import os
import sys

# Projekt-Root in den Pfad, damit `app` importierbar ist (Script liegt in scripts/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.bonus import BonusChallenge
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User


def main() -> int:
    if len(sys.argv) < 2:
        print("Aufruf: python scripts/diagnose_bonus.py <email>")
        return 1
    email = sys.argv[1].strip()

    app = create_app()
    with app.app_context():
        print("=== Bonus-Challenges -> an welcher Challenge haengen sie? ===")
        bonus = db.session.scalars(db.select(BonusChallenge)).all()
        if not bonus:
            print("  (keine Bonus-Challenges vorhanden)")
        for bc in bonus:
            c = db.session.get(Challenge, bc.challenge_id)
            name = c.name if c else "??? (Challenge fehlt!)"
            end = c.end_date if c else "?"
            print(f"  BC#{bc.id} '{bc.description}'  ->  Challenge#{bc.challenge_id} "
                  f"'{name}'  (end {end}, scheduled {bc.scheduled_date})")

        print(f"\n=== Teilnahmen von {email} (alle Status) ===")
        me = db.session.scalar(db.select(User).where(User.email == email))
        if not me:
            print("  !! User mit dieser Email nicht gefunden - Email pruefen.")
            return 2
        parts = db.session.scalars(
            db.select(ChallengeParticipation).where(
                ChallengeParticipation.user_id == me.id
            )
        ).all()
        if not parts:
            print("  (keine Teilnahmen)")
        for p in parts:
            c = db.session.get(Challenge, p.challenge_id)
            print(f"  Challenge#{p.challenge_id} '{c.name if c else '?'}'  "
                  f"status={p.status}")

        print(f"\n=== Was der Bonus-Selektor fuer {email} zeigen wuerde "
              f"(nur status='accepted') ===")
        accepted = db.session.scalars(
            db.select(Challenge)
            .join(ChallengeParticipation,
                  ChallengeParticipation.challenge_id == Challenge.id)
            .where(
                ChallengeParticipation.user_id == me.id,
                ChallengeParticipation.status == "accepted",
            )
            .order_by(Challenge.start_date.desc(), Challenge.id.desc())
        ).all()
        if not accepted:
            print("  (keine) -> Selektor leer, Fallback greift")
        for c in accepted:
            n_bonus = db.session.scalar(
                db.select(db.func.count())
                .select_from(BonusChallenge)
                .where(BonusChallenge.challenge_id == c.id)
            )
            print(f"  Challenge#{c.id} '{c.name}'  (Bonus-Challenges: {n_bonus})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
