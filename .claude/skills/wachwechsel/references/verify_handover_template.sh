#!/usr/bin/env bash
# verify-handover.sh – Start-Verifikation für neue Sessions
#
# Aufruf: ./scripts/verify-handover.sh
#
# Prüft, ob die Übergabe-Anker konsistent sind und meldet Drift sofort.
# Der nächste Agent sollte das als ersten Befehl in einer neuen Session laufen lassen.
#
# Exit 0: alles gut, Session kann starten
# Exit 1: mindestens eine Prüfung fehlgeschlagen, Kontext-Drift möglich
#
# Dieses Template ist projekt-agnostisch. Der Wachwechsel-Skill passt es
# beim ersten Anlegen projektspezifisch an (z.B. konkrete env-Variablen,
# DB-Datei-Pfad, zusätzliche Tool-Checks).

set -euo pipefail

CHECKS_PASSED=0
CHECKS_FAILED=0

pass() {
    echo "  ✅ $1"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
}

fail() {
    echo "  ❌ $1"
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
}

info() {
    echo "  ℹ️  $1"
}

section() {
    echo ""
    echo "── $1 ──"
}

# ─── Git-Zustand ───────────────────────────────────────────────────
section "Git"

if git diff --quiet && git diff --cached --quiet; then
    pass "Working tree ist clean"
else
    fail "Working tree hat uncommitted changes (git status prüfen)"
fi

if [ -n "$(git log --oneline -1 2>/dev/null)" ]; then
    LAST_COMMIT=$(git log -1 --format='%h %s')
    info "Letzter Commit: $LAST_COMMIT"
else
    fail "Keine Commits vorhanden"
fi

# Prüfe, ob Handover-Tag gesetzt wurde (heuristisch)
HANDOVER_TAG=$(git tag -l "handover-*" "pre-*" "milestone-*" 2>/dev/null | tail -1 || true)
if [ -n "$HANDOVER_TAG" ]; then
    info "Letzter Anker-Tag: $HANDOVER_TAG"
fi

# ─── Projekt-Setup ─────────────────────────────────────────────────
section "Projekt-Setup"

if [ -f ".env" ]; then
    pass ".env existiert"
else
    if [ -f ".env.example" ]; then
        fail ".env fehlt – kopiere von .env.example und ergänze Werte"
    else
        info ".env nicht nötig (kein .env.example)"
    fi
fi

if [ -f "CLAUDE.md" ]; then
    if grep -q "## Aktueller Stand" CLAUDE.md; then
        pass "CLAUDE.md enthält 'Aktueller Stand'-Abschnitt"
    else
        fail "CLAUDE.md existiert, aber ohne 'Aktueller Stand'-Abschnitt (Wachwechsel nicht durchgeführt?)"
    fi
else
    fail "CLAUDE.md fehlt"
fi

# ─── bd (beads) ────────────────────────────────────────────────────
section "bd (Issue-Tracker)"

if command -v bd >/dev/null 2>&1; then
    pass "bd ist installiert"
    READY_COUNT=$(bd ready 2>/dev/null | grep -c "^○" || true)
    if [ "$READY_COUNT" -gt 0 ]; then
        pass "bd ready zeigt $READY_COUNT offene Issue(s)"
    else
        info "bd ready leer (keine offene Arbeit oder Epic abgeschlossen)"
    fi
else
    info "bd nicht installiert – übersprungen"
fi

# ─── Workflow-Artefakte ────────────────────────────────────────────
section "Workflow-Artefakte"

if [ -d ".schrammns_workflow" ]; then
    PLAN_COUNT=$(find .schrammns_workflow/plans -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    RESEARCH_COUNT=$(find .schrammns_workflow/research -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    info "Pläne: $PLAN_COUNT · Research: $RESEARCH_COUNT"

    LATEST_PLAN=$(find .schrammns_workflow/plans -name "*.md" 2>/dev/null | sort | tail -1)
    if [ -n "$LATEST_PLAN" ]; then
        info "Neuester Plan: $LATEST_PLAN"
    fi
else
    info ".schrammns_workflow fehlt – übersprungen"
fi

# ─── Dependencies ──────────────────────────────────────────────────
section "Dependencies"

if [ -f "requirements.txt" ]; then
    if [ -d ".venv" ]; then
        pass "Python venv vorhanden (.venv/)"
    else
        fail "Python venv fehlt – 'python -m venv .venv' ausführen"
    fi
fi

# ─── Zusammenfassung ──────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════"
echo "  ✅ Bestanden: $CHECKS_PASSED   ❌ Fehlgeschlagen: $CHECKS_FAILED"
echo "════════════════════════════════════════════════"

if [ "$CHECKS_FAILED" -gt 0 ]; then
    echo ""
    echo "⚠️  Einige Prüfungen fehlgeschlagen – Kontext-Drift möglich."
    echo "    Der scheidende Agent hat möglicherweise einen unvollständigen Wachwechsel hinterlassen."
    echo "    Prüfe die ❌-Einträge oben und frage den Kapitän vor weiteren Schritten."
    exit 1
else
    echo ""
    echo "🏴‍☠️  Alles klar, Wachwechsel ist sauber. Du kannst loslegen."
    echo ""
    echo "Erster Einstieg:"
    echo "    bd memories         # gespeicherten Pointer abrufen"
    echo "    bd ready            # nächstes Issue"
    exit 0
fi
