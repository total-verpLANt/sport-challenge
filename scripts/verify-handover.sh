#!/usr/bin/env bash
# verify-handover.sh – Start-Verifikation für neue Sessions
#
# Aufruf: ./scripts/verify-handover.sh
#
# Exit 0: alles gut, Session kann starten
# Exit 1: mindestens eine Prüfung fehlgeschlagen, Kontext-Drift möglich

set -euo pipefail

CHECKS_PASSED=0
CHECKS_FAILED=0

pass() { echo "  ✅ $1"; CHECKS_PASSED=$((CHECKS_PASSED + 1)); }
fail() { echo "  ❌ $1"; CHECKS_FAILED=$((CHECKS_FAILED + 1)); }
info() { echo "  ℹ️  $1"; }
section() { echo ""; echo "── $1 ──"; }

# ─── Git-Zustand ───────────────────────────────────────────────────
section "Git"

if git diff --quiet && git diff --cached --quiet; then
    pass "Working tree ist clean"
else
    fail "Working tree hat uncommitted changes (git status prüfen)"
fi

LAST_COMMIT=$(git log -1 --format='%h %s')
info "Letzter Commit: $LAST_COMMIT"

HANDOVER_TAG=$(git tag -l "handover-*" "pre-*" "milestone-*" 2>/dev/null | tail -1 || true)
[ -n "$HANDOVER_TAG" ] && info "Letzter Anker-Tag: $HANDOVER_TAG"

# ─── Pflicht-Umgebungsvariablen ────────────────────────────────────
section "Umgebungsvariablen"

if [ -n "${SECRET_KEY:-}" ]; then
    pass "SECRET_KEY gesetzt"
else
    fail "SECRET_KEY fehlt – App startet nicht (config.py wirft KeyError)"
fi

# ─── Projekt-Setup ─────────────────────────────────────────────────
section "Projekt-Setup"

if [ -d ".venv" ]; then
    pass "Python venv vorhanden (.venv/)"
else
    fail "Python venv fehlt – 'python -m venv .venv && pip install -r requirements.txt'"
fi

if [ -f "instance/sport-challenge.db" ]; then
    pass "SQLite-DB vorhanden (instance/sport-challenge.db)"
else
    info "SQLite-DB fehlt – 'flask db upgrade' ausführen (oder FLASK_DEBUG=1 python run.py)"
fi

if [ -f "migrations/alembic.ini" ]; then
    pass "Alembic-Migration initialisiert"
else
    fail "migrations/ fehlt – 'flask db init' ausführen"
fi

if grep -q "## Aktueller Stand" CLAUDE.md 2>/dev/null; then
    pass "CLAUDE.md enthält 'Aktueller Stand'-Abschnitt"
else
    fail "CLAUDE.md ohne 'Aktueller Stand' – Wachwechsel unvollständig?"
fi

# ─── bd (beads) ────────────────────────────────────────────────────
section "bd (Issue-Tracker)"

if command -v bd >/dev/null 2>&1; then
    pass "bd ist installiert"
    READY_COUNT=$(bd ready 2>/dev/null | grep -c "^○" || true)
    if [ "$READY_COUNT" -gt 0 ]; then
        pass "bd ready zeigt $READY_COUNT Issue(s) – direkt loslegen"
    else
        info "bd ready leer"
    fi
else
    fail "bd nicht installiert – siehe https://github.com/nicholasgasior/beads"
fi

# ─── Workflow-Artefakte ────────────────────────────────────────────
section "Workflow-Artefakte"

if [ -d ".schrammns_workflow" ]; then
    LATEST_PLAN=$(find .schrammns_workflow/plans -name "*.md" 2>/dev/null | sort | tail -1)
    [ -n "$LATEST_PLAN" ] && info "Neuester Plan: $LATEST_PLAN"
    [ -f "docs/lessons-learned.md" ] && info "docs/lessons-learned.md vorhanden"
else
    info ".schrammns_workflow fehlt – übersprungen"
fi

# ─── Zusammenfassung ───────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════"
echo "  ✅ Bestanden: $CHECKS_PASSED   ❌ Fehlgeschlagen: $CHECKS_FAILED"
echo "════════════════════════════════════════════════"

if [ "$CHECKS_FAILED" -gt 0 ]; then
    echo ""
    echo "⚠️  Kontext-Drift möglich – ❌-Einträge prüfen."
    exit 1
else
    echo ""
    echo "🏴‍☠️  Alles klar. Erster Einstieg:"
    echo "    bd memories multi-user   # Pointer mit allen Issue-IDs"
    echo "    bd ready                 # nächste Issues"
    exit 0
fi
