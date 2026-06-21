"""Challenge-Statistiken: Ranglisten pro Challenge.

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


def _assign_medal_ranks(entries: list) -> list:
    """Weist absteigend (nach ``value``) sortierten Einträgen Medaillen-Ränge zu.

    Dense-Ranking: gleiche Werte teilen sich denselben ``rank`` (0/1/2 =
    Gold/Silber/Bronze). Ab dem vierten distinkten Wert ist ``rank`` None
    (keine Medaille). Mutiert die übergebenen Dicts in place und gibt die
    Liste zurück.
    """
    rank = -1
    last_value = object()  # Sentinel: garantiert ungleich jedem echten Wert
    for entry in entries:
        if entry["value"] != last_value:
            rank += 1
            last_value = entry["value"]
        entry["rank"] = rank if rank <= 2 else None
    return entries


def _ranking(
    value_by_uid: dict,
    user_by_id: dict,
    fmt,
    participant_ids: list,
    reverse: bool = True,
) -> list:
    """Vollständige Rangliste aller Teilnehmer inkl. Medaillen-Rang.

    Teilnehmer mit echtem Wert werden absteigend (bzw. bei ``reverse=False``
    aufsteigend) sortiert und per Dense-Ranking mit ``rank`` versehen.
    Teilnehmer ohne echten Wert (leer/Null) erscheinen ohne Rang (``"–"``)
    am Ende, alphabetisch nach Anzeigename.
    """
    ranked = [
        (uid, value_by_uid[uid])
        for uid in participant_ids
        if uid in user_by_id and value_by_uid.get(uid)
    ]
    ranked.sort(key=lambda t: t[1], reverse=reverse)
    entries = _assign_medal_ranks(
        [
            {
                "name": user_by_id[uid].display_name,
                "value": v,
                "display": fmt(v),
            }
            for uid, v in ranked
        ]
    )
    rest = sorted(
        (
            uid
            for uid in participant_ids
            if uid in user_by_id and not value_by_uid.get(uid)
        ),
        key=lambda uid: user_by_id[uid].display_name.lower(),
    )
    entries.extend(
        {
            "name": user_by_id[uid].display_name,
            "value": 0,
            "display": "–",
            "rank": None,
        }
        for uid in rest
    )
    return entries


def get_challenge_statistics(challenge: Challenge) -> dict:
    """Aggregiert die Ranglisten-Statistiken einer Challenge.

    Returns:
        {"stats": [{"key", "title", "icon", "top": [{"name", "value",
        "display", "rank"}, ...]}, ...]}

    ``rank`` ist 0/1/2 (Gold/Silber/Bronze, Gleichstände teilen sich den Rang)
    oder None ab dem vierten distinkten Wert.

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
    # Früheste/späteste Startzeit je Teilnehmer (Option B): "Frühaufsteher"
    # meint die früheste je erreichte Uhrzeit, "Nachteule" die späteste –
    # nicht den Durchschnitt (der landete bei gemischten Zeiten irreführend
    # in der Tagesmitte).
    earliest_start = {uid: min(mins) for uid, mins in start_minutes.items() if mins}
    latest_start = {uid: max(mins) for uid, mins in start_minutes.items() if mins}

    # Beliebteste Aktivität (nicht pro User, sondern pro Aktivität)
    by_id = {row.id: row for row in activity_rows}
    liked = sorted(
        ((aid, c) for aid, c in like_counts.items() if c > 0),
        key=lambda t: t[1],
        reverse=True,
    )
    # Beliebteste Aktivität ist aktivitäts- (nicht teilnehmer-)basiert: keine
    # Vollliste, aber dieselbe Tie-Medaillen-Logik. Auf 5 Plätze begrenzt.
    top_liked = []
    for aid, count in liked:
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
    top_liked = _assign_medal_ranks(top_liked)[:5]

    stats = [
        {
            "key": "most_time",
            "title": "Meiste Zeit aktiv",
            "icon": "⏱️",
            "top": _ranking(total_minutes, user_by_id, _fmt_duration, participant_ids),
        },
        {
            "key": "most_activities",
            "title": "Meiste Aktivitäten",
            "icon": "🔥",
            "top": _ranking(
                activity_count, user_by_id, lambda v: f"{v}×", participant_ids
            ),
        },
        {
            "key": "week_streak",
            "title": "Durchgezogen (Wochen)",
            "icon": "📅",
            "top": _ranking(
                week_streak, user_by_id, lambda v: f"{v} Wochen", participant_ids
            ),
        },
        {
            "key": "day_streak",
            "title": "Längste Serie (Tage)",
            "icon": "🔗",
            "top": _ranking(
                day_streak, user_by_id, lambda v: f"{v} Tage", participant_ids
            ),
        },
        {
            "key": "diversity",
            "title": "Vielseitigster Sportler",
            "icon": "🤸",
            "top": _ranking(
                diversity, user_by_id, lambda v: f"{v} Sportarten", participant_ids
            ),
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
            "top": _ranking(
                earliest_start, user_by_id, _fmt_time, participant_ids, reverse=False
            ),
        },
        {
            "key": "night_owl",
            "title": "Nachteule",
            "icon": "🌙",
            "top": _ranking(
                latest_start, user_by_id, _fmt_time, participant_ids, reverse=True
            ),
        },
        {
            "key": "longest_session",
            "title": "Längste Einzel-Session",
            "icon": "🏔️",
            "top": _ranking(max_session, user_by_id, _fmt_duration, participant_ids),
        },
    ]

    # Teilnehmer-Übersicht: Ø Start-Uhrzeit + Ø Dauer je Teilnehmer.
    # Alle akzeptierten Teilnehmer werden gelistet (auch ohne Aktivität);
    # fehlende Werte als "–". Sortiert nach Anzeigename (case-insensitiv).
    participants = []
    for uid in participant_ids:
        count = activity_count[uid]
        participants.append({
            "name": user_by_id[uid].display_name,
            "avg_start": _fmt_time(avg_start[uid]) if uid in avg_start else "–",
            "avg_duration": _fmt_duration(total_minutes[uid] / count) if count else "–",
            "activity_count": count,
        })
    participants.sort(key=lambda p: p["name"].lower())

    return {"stats": stats, "participants": participants}
