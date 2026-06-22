# Changelog

Hier siehst du, was sich in jeder Version der App geändert hat.

## [1.7.0] – 2026-06-22

### Neu
- Registriert sich ein neuer Nutzer und wartet auf Freischaltung, werden die Admins jetzt auch über die Benachrichtigungs-Glocke informiert (zusätzlich zur E-Mail) – ein Klick führt direkt zur Benutzerverwaltung.

## [1.6.0] – 2026-06-21

### Neu
- Wirst du zu einer Challenge eingeladen, bekommst du jetzt eine Benachrichtigung über die Glocke oben rechts – ein Klick bringt dich direkt zur Einladung.

## [1.5.0] – 2026-06-21

### Neu
- Neue Benachrichtigungs-Glocke oben rechts in der Navigationsleiste: Ein roter Badge zeigt dir, wie viele ungelesene Meldungen du hast. Im Dropdown erscheinen deine letzten Benachrichtigungen – ungelesene sind fett hervorgehoben. Du kannst einzelne Einträge per ✕ löschen oder alle auf einmal entfernen. Klickst du auf einen Eintrag, wirst du direkt zum passenden Bereich weitergeleitet und der Eintrag wird als gelesen markiert.

## [1.4.1] – 2026-06-21

### Behoben
- Der Gesundheitsstatus des Servers wurde intern fälschlicherweise als „nicht erreichbar" angezeigt, obwohl die App durchgehend funktionierte. Das ist jetzt korrigiert.

## [1.4.0] – 2026-06-21

### Neu
- Grundlage für das Benachrichtigungssystem gelegt: Die App kann jetzt Meldungen für dich speichern (z. B. Einladungen, Challenge-Ereignisse, Likes). Diese erscheinen demnächst in der Benachrichtigungs-Glocke.

## [1.3.1] – 2026-06-21

### Sicherheit
- Sicherheits-Aktualisierung einer Verschlüsselungs-Komponente, um eine bekannte Schwachstelle zu schließen.

## [1.3.0] – 2026-06-21

### Neu
- Offene Challenge-Einladungen erscheinen jetzt direkt und gut sichtbar ganz oben im Dashboard – mit Wochenziel-Auswahl und Annehmen-/Ablehnen-Buttons. Du musst nicht mehr erst unter „Challenges" suchen. Bei mehreren Einladungen werden alle angezeigt; abgearbeitete Einladungen verschwinden automatisch.

## [1.2.0] – 2026-06-21

### Neu
- Neue Statistik-Karte im Leaderboard: „Meiste Likes verteilt" – du siehst jetzt, wer am großzügigsten Likes an andere (und sich selbst) vergeben hat.

## [1.1.0] – 2026-06-21

### Verbessert
- Medaillen im Leaderboard werden jetzt fair verteilt: Wer punktgleich ist, bekommt dieselbe Medaille (z. B. 3× Gold). Es werden jetzt 5 Plätze angezeigt; über eine aufklappbare Liste kannst du alle Teilnehmer sehen – auch die ohne Wert.

## [1.0.1] – 2026-06-15

### Verbessert
- Interne Verbesserungen und Wartungsarbeiten (Protokolldateien werden jetzt platzsparender archiviert).

## [1.0.0] – 2026-06-15

### Neu
- Offizielles v1.0-Release: Die App ist bereit für den produktiven Einsatz in geschlossenen Gruppen.

### Behoben
- Interne Sicherheitsverbesserung beim Bearbeiten von Abwesenheitsmeldungen.

## [0.19.0] – 2026-06-15

### Neu
- Du kannst dein Konto jetzt selbst löschen: Im Profil findest du eine Konto-Löschung mit Passwort-Bestätigung. Alle deine Daten (Aktivitäten, Medien, Teilnahmen usw.) werden dabei vollständig entfernt.

## [0.18.3] – 2026-06-15

### Behoben
- Bonus-Challenges zeigten bei mehreren gleichzeitig laufenden Challenges manchmal die falsche Challenge an. Das ist jetzt korrigiert – du siehst nur die Bonus-Challenges, an deren Challenge du auch teilnimmst.
- Admins können beim Erstellen einer Bonus-Challenge nun die Ziel-Challenge gezielt auswählen.

### Neu
- Bei mehreren aktiven Challenges gibt es in der Bonus-Übersicht jetzt ein Auswahl-Dropdown, um zwischen den Challenges zu wechseln. Bei nur einer Challenge bleibt die Ansicht wie gewohnt.

## [0.18.2] – 2026-06-15

### Behoben
- „Meine Woche" und die Aktivitäten-Ansicht zeigten bei mehreren gleichzeitig aktiven Challenges manchmal nur eine davon an. Aktivitäten der anderen „verschwanden" optisch. Das ist jetzt behoben.

### Neu
- Bei mehreren aktiven Challenges erscheint in „Meine Woche" und der Aktivitäten-Ansicht ein Dropdown, mit dem du zwischen den Challenges wechseln kannst. Bei nur einer Teilnahme bleibt die Ansicht unverändert.

## [0.18.1] – 2026-06-15

### Behoben
- Bei mehreren gleichzeitig aktiven Challenges konnten eingetragene Aktivitäten, Importe und Abwesenheiten versehentlich in der falschen Challenge landen. Das ist jetzt behoben – die App merkt sich, für welche Challenge du gerade etwas einträgst, und schreibt es korrekt zu.

### Neu
- Beim Eintragen einer Aktivität oder Abwesenheit siehst du bei mehreren Teilnahmen jetzt ein Challenge-Auswahlfeld, um sicherzugehen, dass alles in der richtigen Challenge landet.

## [0.18.0] – 2026-06-13

### Neu
- Neue Tabelle auf der Challenge-Statistik-Seite: „Durchschnittswerte je Teilnehmer" zeigt für alle Teilnehmer die durchschnittliche Startzeit, die durchschnittliche Trainingsdauer und die Anzahl der Aktivitäten. Wer noch keine Aktivität hat, erscheint mit „–".

## [0.17.1] – 2026-06-13

### Verbessert
- „Frühaufsteher" und „Nachteule" im Leaderboard schauen jetzt auf die früheste bzw. späteste Trainingszeit überhaupt – nicht mehr auf den Durchschnitt. Wer wirklich früh trainiert, wird jetzt auch korrekt als Frühaufsteher erkannt.

## [0.17.0] – 2026-06-13

### Neu
- Neue Statistik-Seite pro Challenge mit neun Ranglisten: meiste Trainingszeit, meiste Aktivitäten, längste Wochen-Streak, längste Tages-Streak, vielseitigster Sportler, beliebteste Aktivität, Frühaufsteher, Nachteule und längste Einzelsession.
- Jedes Leaderboard ist jetzt über ein Dropdown in der Navigationsleiste direkt erreichbar.
- Der Dashboard-Feed zeigt Aktivitäten und Abwesenheiten aus allen Challenges, jeweils mit einem Challenge-Badge.
- Bei mehreren gleichzeitig aktiven Challenges hat jede einen eigenen Top-5-Block und Spendentopf. Beendete Challenges erscheinen als kompakte Abschluss-Karte.

### Verbessert
- Alle eingeloggten Nutzer können jetzt jedes Leaderboard und jeden Feed-Eintrag sehen – auch ohne selbst an der jeweiligen Challenge teilzunehmen.

## [0.16.7] – 2026-06-08

### Verbessert
- Das Dashboard lädt deutlich schneller: Die Strafberechnung für das Leaderboard wurde von vielen kleinen Einzelabfragen auf wenige gebündelte Datenbankabfragen umgestellt. Das Ergebnis ist dasselbe, aber die Ladezeit sinkt spürbar – besonders bei vielen Teilnehmern und langen Challenges.

## [0.16.6] – 2026-06-08

### Sicherheit
- Hochgeladene Bilder und Videos werden jetzt inhaltlich geprüft: Eine Datei mit falscher Endung oder manipuliertem Inhalt wird abgelehnt. Damit wird verhindert, dass getarnte Dateien hochgeladen werden können.

## [0.16.5] – 2026-06-08

### Sicherheit
- Der „Angemeldet bleiben"-Cookie wird jetzt genauso sicher übertragen wie der Anmelde-Cookie – ausschließlich über verschlüsselte HTTPS-Verbindungen.

## [0.16.4] – 2026-06-08

### Sicherheit
- Es war möglich, ein fremdes Konto durch absichtlich falsche Login-Versuche temporär zu sperren. Das ist jetzt behoben: Ein korrektes Passwort entsperrt das Konto immer. Der Brute-Force-Schutz greift jetzt auf IP-Ebene, nicht mehr auf Konto-Ebene.

## [0.16.3] – 2026-06-08

### Behoben
- Bilder im Dashboard-Feed und in der Aktivitätsdetailansicht ließen sich nach dem letzten Sicherheits-Update nicht mehr in der Lightbox öffnen – stattdessen war nur ein leeres Fenster zu sehen. Das ist jetzt behoben.
- Bilder in der Aktivitätsdetailansicht wurden mittig abgeschnitten angezeigt. Jetzt ist immer das vollständige Bild sichtbar, einheitlich mit der Video-Darstellung.

## [0.16.2] – 2026-06-08

### Sicherheit
- Hochgeladene Bilder und Videos sind jetzt nicht mehr über eine direkte URL ohne Login abrufbar. Medien werden ausschließlich an eingeloggte Nutzer ausgeliefert.

### Verbessert
- Hochgeladene Dateien werden an einem sichereren Speicherort abgelegt (außerhalb des öffentlich zugänglichen Bereichs der App).

## [0.16.1] – 2026-06-08

### Sicherheit
- Links in E-Mails (z. B. Passwort-Reset, Freischaltung) werden nicht mehr aus dem Browser-Anfrage-Header abgeleitet, den ein Angreifer manipulieren könnte. Stattdessen wird immer die konfigurierte App-Adresse verwendet.
- Neue Einstellung für erlaubte Hostnamen: Anfragen von fremden Domains werden mit einem Fehler abgewiesen.

## [0.16.0] – 2026-06-08

### Verbessert
- Die „Krankmeldung" heißt jetzt „Abwesenheit" – denn es gibt mehr Gründe, mal nicht dabei zu sein (z. B. Urlaub oder Dienstreise). Die Strafberechnung bleibt unverändert.

### Neu
- Beim Eintragen einer Abwesenheit kannst du jetzt optional einen Grund angeben (bis zu 500 Zeichen).
- Abwesenheiten erscheinen jetzt im Dashboard-Feed und können von anderen geliket werden.

### Behoben
- Ein Fehler, der den Dashboard-Feed bei Aktivitäten mit hochgeladenen Medien zum Absturz gebracht hätte, wurde behoben.

## [0.15.2] – 2026-06-05

### Verbessert
- Interne Verbesserung beim E-Mail-Versand an Admins bei Neuregistrierungen (effizienter, ohne Auswirkung auf Nutzererlebnis).

## [0.15.1] – 2026-06-05

### Behoben
- Schlägt die Benachrichtigungs-E-Mail an einen Admin bei einer Neuregistrierung fehl, werden die anderen Admins jetzt trotzdem benachrichtigt.

## [0.15.0] – 2026-05-27

### Neu
- Im Dashboard siehst du jetzt neben dem Like-Herz die Spitznamen der Personen, denen deine Aktivität gefällt (z. B. „Tick, Trick und Track gefällt das"). Ab 6 Likern wird abgekürzt.

## [0.14.0] – 2026-05-19

### Neu
- „Meine Woche" unterstützt jetzt mehrere Abwesenheitsmeldungen in derselben Woche: Jede Meldung hat eine eigene Bearbeiten- und Löschen-Funktion, und du kannst weitere Meldungen direkt hinzufügen.
- Der Karten-Header zeigt bei mehreren Meldungen eine kompakte Übersicht aller Zeiträume.

## [0.13.2] – 2026-05-19

### Behoben
- In „Meine Woche" werden Tage mit Abwesenheitsmeldung jetzt mit einem Badge markiert und farbig hervorgehoben. Aktivitäten an diesen Tagen werden weiterhin korrekt angezeigt.
- „Meine Woche" stürzte nicht mehr ab, wenn mehrere Abwesenheitsmeldungen in dieselbe Woche fallen.

## [0.13.1] – 2026-05-11

### Sicherheit
- Passwort-Reset-Links können jetzt nur noch einmal verwendet werden. Nach erfolgreichem Passwortwechsel ist der Link automatisch ungültig.

## [0.13.0] – 2026-05-06

### Neu
- Abwesenheitsmeldungen funktionieren jetzt mit einem Von/Bis-Datumsmodell – du kannst genaue Zeiträume angeben statt nur ganze Wochen.
- Abwesenheiten für zukünftige Zeiträume können vorab eingetragen werden.
- Das Enddatum einer Abwesenheit lässt sich nachträglich anpassen (z. B. bei Frühgenesung).
- Sich überschneidende Abwesenheitsmeldungen desselben Teilnehmers werden abgelehnt.

### Verbessert
- Abwesenheitsmeldungen werden auf die Laufzeit der Challenge begrenzt.

## [0.12.1] – 2026-05-02

### Neu
- Trainingsnotizen lassen sich jetzt auch nachträglich über die „Medien hinzufügen"-Seite oder direkt auf der Aktivitäts-Detailseite bearbeiten oder löschen.

### Behoben
- Die Seite „Passwort vergessen" war durch eine falsch gesetzte Zugriffsbeschränkung nicht mehr aufrufbar. Das ist jetzt behoben.
- Das Zugriffs-Limit greift jetzt korrekt auch hinter dem Cloudflare-Schutz.

## [0.12.0] – 2026-05-02

### Neu
- Passwort vergessen? Über den Link auf der Login-Seite kannst du einen Reset-Link per E-Mail anfordern. Der Link ist eine Stunde gültig.
- Admins erhalten bei jeder Neuregistrierung eine E-Mail-Benachrichtigung.
- Nach der Freischaltung durch einen Admin erhältst du eine Bestätigungs-E-Mail.

## [0.11.0] – 2026-05-02

### Verbessert
- Die App läuft jetzt in einem Docker-Container und kann damit zuverlässiger und einfacher auf einem Server betrieben werden.
- Automatische Bereitstellung neuer Versionen über eine CI/CD-Pipeline.
- HTTP-Zugriffe werden protokolliert (für die Administration des Servers).

### Behoben
- Interne Korrekturen an der Bereitstellungskonfiguration.

## [0.10.0] – 2026-05-01

### Neu
- Beim Eintragen einer Bonus-Challenge-Zeit ist jetzt ein Video-Beweis erforderlich (MP4, MOV oder WebM, max. 50 MB).
- Das Aufnahmedatum wird automatisch aus den Video-Metadaten ausgelesen und in der Rangliste angezeigt.
- Neue Gesamtwertung über alle Bonus-Runden: Die beste Einzelzeit pro Person zählt (Wanderpokal-Prinzip).
- Admins können beim Erstellen einer Bonus-Challenge mehrere Termine auf einmal festlegen.
- Einsendungen sind jederzeit möglich, nicht nur bis zu einem Stichtag.

### Behoben
- Gelöschte Videos wurden nicht immer vollständig vom Server entfernt. Das ist jetzt korrigiert.

## [0.9.0] – 2026-04-30

### Neu
- Teilnehmer können eigene Abwesenheitsmeldungen selbst löschen (mit Bestätigungsdialog).
- Admins können Abwesenheitsmeldungen, Aktivitäten, Bonus-Challenges und ganze Challenges inkl. aller zugehörigen Daten löschen.

### Behoben
- Beim Löschen eines Nutzers blieben hochgeladene Mediendateien auf dem Server zurück. Das wird jetzt vollständig bereinigt.

## [0.8.2] – 2026-04-29

### Neu
- Partielle Abwesenheit: Du kannst jetzt 1 bis 7 einzelne Tage pro Woche als krank melden (statt immer die gesamte Woche).
- Abwesenheitsmeldungen können rückwirkend für vergangene Wochen eingetragen werden.
- Abwesenheitsmeldung auch direkt über den „Eintragen"-Tab mit freier Datumswahl erreichbar.
- Formel: Je 2 Krankentage zählt ein Aktivitäts-Abzug vom Wochenziel; ab 6 Tagen entfällt die Strafe komplett. Das effektive Wochenziel wird in der Fortschrittsanzeige ausgewiesen.
- Eine bestehende Abwesenheitsmeldung kann über dasselbe Formular korrigiert werden.

## [0.8.1] – 2026-04-29

### Sicherheit
- Sicherheitslücke behoben: Dateinamen von hochgeladenen Medien konnten theoretisch schadhaften Code enthalten. Die Anzeige ist jetzt sicher, und Dateinamen werden beim Speichern bereinigt.

## [0.8.0] – 2026-04-29

### Neu
- Neuer Social-Feed im Dashboard: Die 10 neuesten Aktivitäten aller Challenge-Teilnehmer werden angezeigt – mit Sport-Typ, Dauer, Datum, einem zufälligen Motivationsspruch, Fotos/Videos und Trainingsnotiz. Über „mehr laden" kannst du weitere Einträge nachladen.
- Like-Button pro Aktivität: Herz anklicken, um eine Aktivität zu liken (und wieder zu entliken).
- Top-5-Leaderboard direkt auf der Dashboard-Startseite; vollständiges Leaderboard über den Navbar-Link erreichbar.

## [0.7.7] – 2026-04-29

### Neu
- Beim Eintragen einer Aktivität kannst du jetzt eine optionale Trainingsnotiz hinzufügen (bis zu 2000 Zeichen). Die Notiz erscheint in der Detailansicht und als Kurzvorschau in der Wochenansicht.

## [0.7.6] – 2026-04-29

### Neu
- Du kannst dein Passwort jetzt direkt in deinem Profil selbst ändern – mit Eingabe des alten Passworts als Bestätigung.

## [0.7.5] – 2026-04-29

### Verbessert
- Interne Verbesserungen und Wartungsarbeiten.

## [0.7.4] – 2026-04-29

### Verbessert
- Interne Verbesserungen am Server-Setup für stabileren Betrieb.

## [0.7.3] – 2026-04-29

### Neu
- Admin: Neue Detailseite pro Nutzer mit E-Mail, Spitzname, Rolle, Freischaltungsstatus und verbundenen Integrationen.
- Admin: Konten sperren und entsperren (gesperrte Nutzer können sich nicht einloggen).
- Admin: Passwort eines Nutzers direkt zurücksetzen.
- Admin: Nutzerkonto mit zweistufiger Bestätigung löschen (inkl. aller zugehörigen Daten).

### Sicherheit
- Löschen ist blockiert, wenn der Nutzer Challenges erstellt hat (Datenverlust-Schutz). Admins können sich selbst nicht sperren oder löschen.

## [0.7.2] – 2026-04-29

### Neu
- Admins können andere Nutzer in der Benutzerverwaltung zum Admin machen (und umgekehrt).

### Sicherheit
- Es ist nicht mehr möglich, den letzten Admin zu entfernen.

## [0.7.1] – 2026-04-29

### Neu
- Neues App-Icon (Läufer-Symbol) – passt sich automatisch an Hell- und Dunkelmodus an.

## [0.7.0] – 2026-04-29

### Neu
- Dunkelmodus: Ein Klick auf den 🌙/☀️-Button in der Navigationsleiste wechselt zwischen hellem und dunklem Design. Die Einstellung wird gespeichert und gilt auch beim nächsten Besuch.

## [0.6.0] – 2026-04-28

### Neu
- Die aktuelle Versionsnummer wird in der Navigationsleiste angezeigt – ein Klick öffnet diese Changelog-Seite.

## [0.5.0] – 2026-04-27

### Neu
- Bilder und Videos lassen sich jetzt in einer Lightbox-Vollbild-Ansicht öffnen.
- Einzelne Medien können aus einer Aktivität gelöscht werden.

## [0.4.0] – 2026-04-27

### Neu
- Mehrere Fotos und Videos (bis je 50 MB) können per Drag-and-Drop oder Datei-Auswahl zu einer Aktivität hochgeladen werden.
- Medien können auch nachträglich zu einer bestehenden Aktivität hinzugefügt werden.
- Medien-Galerie in der Aktivitätsdetailansicht sowie Thumbnails in der Wochen- und Nutzeransicht.

### Sicherheit
- Schutz gegen manipulierte Dateipfade beim Löschen von Medien.

## [0.3.0] – 2026-04-27

### Neu
- Challenges können eine öffentliche URL erhalten und als öffentlich oder privat markiert werden.

## [0.2.0] – 2026-04-26

### Neu
- Challenge-System mit Leaderboard und Strafpunkten.
- Wochenziele (2 oder 3 Tage), Abwesenheitsmeldungen und manuelle Strafanpassungen durch Admins.
- Bonus-Challenges mit Zeitwertung und Ranking.
- Aktivitäten eintragen: manuell, per Garmin-Import oder Strava-Import.
- Screenshot-Upload pro Aktivität.

## [0.1.0] – 2026-04-24

### Neu
- Mehrere Nutzer können sich registrieren und einloggen.
- Verbindung zu Garmin Connect und Strava (OAuth).
- Sicher verschlüsselte Speicherung von Zugangsdaten.
- Admin-Bereich zur Benutzerverwaltung.

## [0.0.1] – 2026-04-01

### Neu
- Erste Version: Aktivitätsübersicht aus Garmin Connect mit Wochenansicht und 30-Minuten-Filter.
