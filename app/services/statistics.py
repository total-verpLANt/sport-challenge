"""Challenge-Statistiken: Top-3-Ranglisten pro Challenge.

Alle Daten werden in wenigen Bulk-Queries geladen und im Speicher aggregiert
(kein N+1), analog zum Vorbild ``weekly_summary.get_challenge_summary``.
"""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.activity import Activity, ActivityLike
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_period import SickPeriod
from app.services.penalty import get_week_mondays

# Ein Tag gilt als "erfüllt", wenn die Summe der Aktivitätsdauer >= 30 min ist
# (identisch zu penalty.count_fulfilled_days).
FULFILLED_THRESHOLD_MINUTES = 30


def _fmt_duration(minutes: float) -> str:
    """Minuten als 'X h Y min' / 'X h' / 'Y min' formatieren."""
    total = int(round(minutes))
    h, m = divmod(total, 60)
    if h and m:
        return f"{h} h {m} min"
    if h:
        return f"{h} h"
    return f"{m} min"


def _fmt_time(minutes_of_day: float) -> str:
    """Tagesminuten (0–1439) als HH:MM formatieren."""
    h, m = divmod(int(round(minutes_of_day)), 60)
    return f"{h % 24:02d}:{m:02d}"


def _is_sick_week(periods: list, week_start: date) -> bool:
    """True, wenn ein Krankheitszeitraum die Woche überlappt."""
    week_end = week_start + timedelta(days=6)
    return any(
        p.start_date <= week_end and p.end_date >= week_start for p in periods
    )


def _fulfilled_in_week(fulfilled_set: set, uid: int, week_start: date) -> int:
    """Erfüllte Tage einer Woche aus dem vorab geladenen (user_id, date)-Set."""
    return sum(
        1
        for i in range(7)
        if (uid, week_start + timedelta(days=i)) in fulfilled_set
    )


def _longest_week_streak(
    fulfilled_set: set,
    sick_periods: list,
    uid: int,
    weeks: list[date],
    weekly_goal: int,
    today: date,
) -> int:
    """Längste Folge erfüllter Wochen ohne Fehltage.

    Eine Woche zählt als erfüllt, wenn fulfilled_days >= weekly_goal. Eine
    Krankheit/Abwesenheit in einer Woche bricht die Serie (sie gilt nicht als
    "durchgezogen"). Die noch laufende (offene) Woche bricht nicht, solange das
    Ziel theoretisch noch erreichbar ist – sie ist erst entschieden, sobald vorbei.
    """
    longest = current = 0
    for week_start in weeks:
        if _is_sick_week(sick_periods, week_start):
            current = 0  # Abwesenheit bricht die Serie
            continue
        fulfilled = _fulfilled_in_week(fulfilled_set, uid, week_start)
        if fulfilled >= weekly_goal:
            current += 1
            longest = max(longest, current)
        elif week_start + timedelta(days=6) >= today:
            continue  # offene Woche, noch nicht entschieden
        else:
            current = 0
    return longest


def _longest_day_streak(dates: set) -> int:
    """Längste Folge aufeinanderfolgender Kalendertage (strenge Variante)."""
    if not dates:
        return 0
    ordered = sorted(dates)
    longest = current = 1
    for prev, cur in zip(ordered, ordered[1:]):
        if (cur - prev).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _top3(value_by_uid: dict, user_by_id: dict, fmt, reverse: bool = True) -> list:
    """Top-3-Rangliste aus {uid: value}; leere/Null-Werte werden ignoriert."""
    items = [(uid, v) for uid, v in value_by_uid.items() if v]
    items.sort(key=lambda t: t[1], reverse=reverse)
    return [
        {
            "name": user_by_id[uid].display_name,
            "value": v,
            "display": fmt(v),
        }
        for uid, v in items[:3]
        if uid in user_by_id
    ]


def get_challenge_statistics(challenge: Challenge) -> dict:
    """Aggregiert Top-3-Statistiken einer Challenge.

    Returns:
        {"stats": [{"key", "title", "icon", "top": [{"name", "value",
        "display"}, ...]}, ...]}

    Performance: konstante Anzahl Bulk-Queries (Teilnehmer, Aktivitäten,
    Like-Counts, erfüllte Tage, Krankheitszeiträume) + reine In-Memory-Aggregation.
    """
    today = date.today()
    weeks = get_week_mondays(challenge.start_date, min(today, challenge.end_date))

    # 1. Teilnehmer (accepted + bailed_out) inkl. User – wie weekly_summary
    participations = (
        db.session.execute(
            db.select(ChallengeParticipation)
            .where(
                ChallengeParticipation.challenge_id == challenge.id,
                ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
            )
            .options(joinedload(ChallengeParticipation.user))
        )
        .scalars()
        .all()
    )
    user_by_id = {p.user.id: p.user for p in participations}
    goal_by_id = {p.user_id: p.weekly_goal for p in participations}
    participant_ids = list(user_by_id.keys())

    # Akkumulatoren
    total_minutes: dict[int, int] = defaultdict(int)
    activity_count: dict[int, int] = defaultdict(int)
    sport_types: dict[int, set] = defaultdict(set)
    max_session: dict[int, int] = defaultdict(int)
    start_minutes: dict[int, list] = defaultdict(list)
    days_by_user: dict[int, set] = defaultdict(set)

    activity_rows = []
    like_counts: dict[int, int] = {}
    fulfilled_set: set[tuple[int, date]] = set()
    sick_by_user: dict[int, list] = defaultdict(list)

    if participant_ids:
        # 2. Alle Aktivitäten der Challenge – eine Query, nur benötigte Spalten
        activity_rows = db.session.execute(
            db.select(
                Activity.id,
                Activity.user_id,
                Activity.activity_date,
                Activity.duration_minutes,
                Activity.sport_type,
                Activity.started_at,
            ).where(
                Activity.challenge_id == challenge.id,
                Activity.user_id.in_(participant_ids),
            )
        ).all()

        for row in activity_rows:
            uid = row.user_id
            total_minutes[uid] += row.duration_minutes
            activity_count[uid] += 1
            if row.sport_type and row.sport_type.strip():
                sport_types[uid].add(row.sport_type.strip().lower())
            if row.duration_minutes > max_session[uid]:
                max_session[uid] = row.duration_minutes
            if row.started_at is not None:
                start_minutes[uid].append(
                    row.started_at.hour * 60 + row.started_at.minute
                )

        # 3. Like-Counts pro Aktivität – eine Query
        activity_ids = [row.id for row in activity_rows]
        if activity_ids:
            like_counts = dict(
                db.session.execute(
                    db.select(ActivityLike.activity_id, func.count(ActivityLike.id))
                    .where(ActivityLike.activity_id.in_(activity_ids))
                    .group_by(ActivityLike.activity_id)
                ).all()
            )

        # 4. Erfüllte Tage (≥30 min) – GROUP BY/HAVING, eine Query
        fulfilled_rows = db.session.execute(
            db.select(Activity.user_id, Activity.activity_date)
            .where(
                Activity.challenge_id == challenge.id,
                Activity.user_id.in_(participant_ids),
            )
            .group_by(Activity.user_id, Activity.activity_date)
            .having(func.sum(Activity.duration_minutes) >= FULFILLED_THRESHOLD_MINUTES)
        ).all()
        for uid, d in fulfilled_rows:
            fulfilled_set.add((uid, d))
            days_by_user[uid].add(d)

        # 5. Krankheitszeiträume – eine Query, pro User gruppiert
        for sp in db.session.scalars(
            db.select(SickPeriod).where(
                SickPeriod.challenge_id == challenge.id,
                SickPeriod.user_id.in_(participant_ids),
            )
        ).all():
            sick_by_user[sp.user_id].append(sp)

    # Streaks (in-memory)
    week_streak = {
        uid: _longest_week_streak(
            fulfilled_set, sick_by_user[uid], uid, weeks, goal_by_id[uid], today
        )
        for uid in participant_ids
    }
    day_streak = {uid: _longest_day_streak(days_by_user[uid]) for uid in participant_ids}
    diversity = {uid: len(s) for uid, s in sport_types.items()}
    avg_start = {
        uid: sum(mins) / len(mins) for uid, mins in start_minutes.items() if mins
    }

    # Beliebteste Aktivität (nicht pro User, sondern pro Aktivität)
    by_id = {row.id: row for row in activity_rows}
    liked = sorted(
        ((aid, c) for aid, c in like_counts.items() if c > 0),
        key=lambda t: t[1],
        reverse=True,
    )
    top_liked = []
    for aid, count in liked[:3]:
        row = by_id.get(aid)
        if row is None or row.user_id not in user_by_id:
            continue
        name = user_by_id[row.user_id].display_name
        sport = row.sport_type or "Aktivität"
        when = row.activity_date.strftime("%d.%m.")
        top_liked.append(
            {
                "name": f"{sport} am {when} – {name}",
                "value": count,
                "display": f"{count} ❤️",
            }
        )

    stats = [
        {
            "key": "most_time",
            "title": "Meiste Zeit aktiv",
            "icon": "⏱️",
            "top": _top3(total_minutes, user_by_id, _fmt_duration),
        },
        {
            "key": "most_activities",
            "title": "Meiste Aktivitäten",
            "icon": "🔥",
            "top": _top3(activity_count, user_by_id, lambda v: f"{v}×"),
        },
        {
            "key": "week_streak",
            "title": "Durchgezogen (Wochen)",
            "icon": "📅",
            "top": _top3(week_streak, user_by_id, lambda v: f"{v} Wochen"),
        },
        {
            "key": "day_streak",
            "title": "Längste Serie (Tage)",
            "icon": "🔗",
            "top": _top3(day_streak, user_by_id, lambda v: f"{v} Tage"),
        },
        {
            "key": "diversity",
            "title": "Vielseitigster Sportler",
            "icon": "🤸",
            "top": _top3(diversity, user_by_id, lambda v: f"{v} Sportarten"),
        },
        {
            "key": "most_liked",
            "title": "Beliebteste Aktivität",
            "icon": "❤️",
            "top": top_liked,
        },
        {
            "key": "early_bird",
            "title": "Frühaufsteher",
            "icon": "🌅",
            "top": _top3(avg_start, user_by_id, _fmt_time, reverse=False),
        },
        {
            "key": "night_owl",
            "title": "Nachteule",
            "icon": "🌙",
            "top": _top3(avg_start, user_by_id, _fmt_time, reverse=True),
        },
        {
            "key": "longest_session",
            "title": "Längste Einzel-Session",
            "icon": "🏔️",
            "top": _top3(max_session, user_by_id, _fmt_duration),
        },
    ]

    return {"stats": stats}
