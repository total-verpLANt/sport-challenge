# Ghost-Message – Nachricht vom scheidenden Wachoffizier

Eine **persönliche, knappe Notiz** vom scheidenden Agenten an den nachfolgenden. Sie ergänzt die formalen Tabellen um Kontext, den man sonst nur im Gespräch vermittelt.

## Zweck

Der nächste Agent liest CLAUDE.md, bekommt Struktur. Die Ghost-Message gibt ihm **Gefühl** für die Lage – was war schwierig, wo war Unsicherheit, was ist bewusst **so** entschieden worden.

Es ist die Gelegenheit zu sagen: *"Ich hätte das fast anders gemacht, aber X hat mich überzeugt, Y zu wählen."* Solche Sätze stehen nirgendwo sonst.

## Einbettung in CLAUDE.md

Unter dem "Aktueller Stand"-Abschnitt, als letzter Unter-Block vor "Build & Test":

```markdown
### Nachricht vom scheidenden Wachoffizier (YYYY-MM-DD)

> <Block-Zitat mit der Nachricht, 2–6 Sätze.>
```

Alte Nachrichten werden beim nächsten Wachwechsel **ersetzt**, nicht angesammelt. Wenn eine alte Nachricht unersetzbar wertvoll ist (z.B. fundamentale Entscheidung), gehört sie als Lesson ins `docs/lessons-learned.md`.

## Gute Ghost-Messages (Beispiele)

### Beispiel 1 – Entscheidung mit Kontext

> *"Ich habe heute den Rebuild-Plan gemacht und die Issues in bd angelegt. Am längsten beschäftigt hat mich die Frage, ob Komoot reinsoll – ich habe mich dagegen entschieden, weil die inoffizielle API ToS-Risiko hat und wir Credentials speichern müssten. Alternative ist ein GPX-Upload-Feature, das kommt in einen eigenen Plan. Falls du anderer Meinung bist: `docs/lessons-learned.md` hat den Research-Link."*

**Warum gut:** Nennt die Entscheidung, den Grund, die Alternative, und wo der Nachfolger die Belege findet.

### Beispiel 2 – Warnung vor Stolperstelle

> *"Die Wave-0-Issues (I-01 bis I-03) sehen trivial aus, sind sie aber nicht: Wenn du I-02 (SECRET_KEY-Fallback entfernen) machst, bricht jede lokale Dev-Umgebung, die die Variable nicht gesetzt hat – auch Tests. Ich habe I-02 bewusst NICHT gestartet, weil ich erst noch die Test-Infrastruktur (I-23) sehen wollte. Vielleicht willst du die Reihenfolge überdenken."*

**Warum gut:** Warnt vor einer nicht-offensichtlichen Kopplung und erklärt, warum der scheidende Agent selbst nicht weitergegangen ist.

### Beispiel 3 – Offene Unsicherheit

> *"Beim Verdrahten der bd-Dependencies war ich mir bei I-14 → I-09 unsicher. Hab's letztendlich weggelassen, weil BaseConnector keine echte Code-Kopplung an die App Factory hat. Könnte aber sein, dass die Wave-Struktur dadurch kosmetisch kaputtgeht. Falls dir die Ready-Queue merkwürdig vorkommt: das ist der Grund."*

**Warum gut:** Dokumentiert eine bewusste Entscheidung, die beim Lesen seltsam aussehen könnte.

## Schlechte Ghost-Messages (vermeiden)

### Anti-Beispiel 1 – redundant zur Tabelle

> ❌ *"Hi, ich habe heute 25 Issues angelegt und 32 Dependencies. Wave 0 ist bereit. Nächster Schritt: I-01."*

Das steht alles schon im Handover-Report. Nichts gelernt.

### Anti-Beispiel 2 – zu vage

> ❌ *"War ein interessanter Tag, viel gemacht. Viel Erfolg!"*

Kein Kontext, keine Warnung, kein Lerneffekt. Weglassen ist besser.

### Anti-Beispiel 3 – Emotion ohne Substanz

> ❌ *"Der Kapitän war heute in guter Stimmung, hat viel entschieden. Hoffentlich bleibt das so."*

Persönliche Beobachtung ohne Arbeits-Relevanz. Gehört nicht ins Repo.

## Faustregel

Die Ghost-Message sollte **min. einen Satz** enthalten, der mit *"weil"*, *"obwohl"*, *"falls"* oder *"ich war mir unsicher, ob"* beginnt. Das zwingt zur Reflexion über Entscheidungen, nicht nur zur Aufzählung von Aktionen.
