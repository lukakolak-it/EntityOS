# Target Radar Pipeline

## Ziel

Die Pipeline beschreibt den fachlichen Datenfluss von der Suche nach Targets bis zur manuellen Entscheidung.

Sie ist der Orchestrator der Anwendung. Die einzelnen Engines bleiben voneinander getrennt und werden nur ueber klare Datenobjekte verbunden.

## Ablauf

```text
Profil + Suchprofil
  -> LeadEngine
  -> Target Import
  -> Fetcher / Extractor
  -> RatingEngine
  -> DraftEngine
  -> Review Queue
  -> manuelle Entscheidung

Review Queue
  -> DraftEngine erneut
  -> RatingEngine erneut
  -> LeadEngine erneut mit angepasstem Suchprofil
  -> Blacklist / Denylist
```

## 1. Profil und Suchprofil

Eingabe fuer den Lauf.

Enthaelt:

- Zielrolle oder Opportunity-Typ
- Regionen
- Tech- und Fachkeywords
- Branchenbegriffe
- Ausschlussbegriffe
- optionale manuelle Query

## 2. LeadEngine

Aufgabe: passende Target-Kandidaten finden.

Die LeadEngine:

- erzeugt viele kurze Queries aus Suchprofil-Attributen,
- nutzt Provider wie Brave,
- wendet Request-Budget an,
- speichert SERP-Ergebnisse,
- filtert bekannte schlechte Quellen,
- dedupliziert nach Domain,
- uebergibt brauchbare Kandidaten an den Target Import.

Output:

- Target-Kandidaten
- Source Evidence
- Query-Herkunft
- Block- oder Importstatus

## 3. Target Import

Aufgabe: Kandidaten in lokale Targets ueberfuehren.

Der Import:

- normalisiert URLs,
- extrahiert Domains,
- erkennt vorhandene Targets,
- verhindert Dubletten,
- markiert die Quelle, z. B. `serp:brave`.

Output:

- lokale Targets

## 4. Fetcher / Extractor

Aufgabe: relevante Inhalte eines Targets sammeln.

Der Fetcher:

- laedt die Homepage,
- erkennt relevante interne Links,
- laedt wenige passende Unterseiten,
- extrahiert sichtbaren Text,
- extrahiert Kontakt-E-Mails und Links.

Output:

- Target Pages
- Textkontext
- Kontakt- und Link-Signale

## 5. RatingEngine

Aufgabe: fachliche Passung bewerten.

Die RatingEngine:

- bewertet Regeln und Keywords,
- nutzt optional AI Scoring,
- erzeugt Gruende und Risiken mit Quellen,
- empfiehlt eine Aktion.

Moegliche Aktionen:

- `skip`
- `review`
- `draft`

Output:

- Target Score
- Reasons
- Risks
- Recommended Action

## 6. DraftEngine

Aufgabe: nur fuer passende Targets einen Action Draft erzeugen.

Die DraftEngine:

- nutzt Profil, Target, Score und Quellenkontext,
- erzeugt keinen automatischen Versand,
- setzt Drafts auf `needs_review`,
- vermeidet erfundene Ansprechpartner und unbelegte Aussagen.

Output:

- Action Draft

## 7. Review Queue

Aufgabe: menschliche Entscheidung.

Der Nutzer kann:

- Draft pruefen,
- Target verwerfen,
- Target blacklisten,
- Draft bearbeiten,
- Draft freigeben.

Die Review Queue ist der Sicherheitsanker der Anwendung. Kein Draft wird automatisch versendet.

## 8. Lauf-Konzept

Ein Pipeline-Lauf ist eine nachvollziehbare Ausfuehrung fuer genau ein Suchprofil und einen konkreten Parametersatz.

Ein Lauf speichert:

- Suchprofil-ID
- Preset / Use Case
- Start- und Endzeit
- Laufmodus
- Request-Budget
- verbrauchtes Budget
- ausgefuehrte Queries
- betroffene Targets
- Fehler und Teilfehler
- Ergebniszaehler

Moegliche Laufmodi:

- `explore`: neue Targets suchen, breites Query-Fanout
- `focused`: validiertes Suchprofil gezielt ausfuehren
- `refresh`: bestehende Targets und neue Treffer aktualisieren
- `rerun`: gezielte Wiederverarbeitung nach Review-Aktion

## 9. Laufstatus

Ein Lauf ist nicht nur erfolgreich oder fehlgeschlagen.

Moegliche Statuszustaende:

- `pending`: Lauf ist angelegt, aber noch nicht gestartet.
- `running`: Lauf verarbeitet aktiv Schritte.
- `paused`: Lauf wurde kontrolliert angehalten.
- `completed`: Lauf wurde ohne kritische Fehler beendet.
- `completed_with_errors`: Lauf wurde beendet, aber einzelne Targets oder Schritte sind fehlgeschlagen.
- `failed`: Lauf konnte nicht sinnvoll fortgesetzt werden.
- `cancelled`: Lauf wurde manuell abgebrochen.

Ein Fehler bei einem einzelnen Target soll den gesamten Lauf nicht stoppen, solange weitere Targets sinnvoll verarbeitet werden koennen.

## 10. Target-Status im Lauf

Jedes Target kann innerhalb eines Laufs einen eigenen Fortschritt haben.

Beispiele:

- `candidate`: von der LeadEngine gefunden
- `review_source`: Kontextquelle, nicht als primaeres Target importiert
- `blocked_source`: Quelle ist durch Denylist blockiert
- `imported`: als Target importiert
- `existing`: Target existiert bereits
- `fetch_pending`: Fetch noch offen
- `fetch_partial`: mindestens eine Seite geladen, mindestens eine fehlgeschlagen
- `fetch_failed`: keine brauchbare Seite erreichbar
- `rating_pending`: bereit fuer Bewertung
- `rating_partial`: Rule Score vorhanden, AI Score fehlt
- `rating_failed`: Bewertung nicht moeglich
- `draft_pending`: bereit fuer Draft-Erzeugung
- `draft_failed`: Draft konnte nicht erzeugt werden
- `needs_review`: wartet auf manuelle Pruefung
- `rejected`: Nutzer hat verworfen
- `approved`: Nutzer hat freigegeben
- `blacklisted`: Nutzer hat Target oder Domain ausgeschlossen

Diese Status duerfen nebeneinander mit den bestehenden Tabellen wachsen. Wichtig ist zuerst die fachliche Semantik.

## 11. Fehlerverhalten

Die Pipeline muss Teilfehler isolieren.

### LeadEngine-Fehler

Wenn ein Provider-Request fehlschlaegt:

- die betroffene Query wird als `failed` gespeichert,
- Fehlertext und Provider werden gespeichert,
- das Budget fuer diese Query gilt als verbraucht,
- der Lauf setzt mit der naechsten Query fort,
- wenn alle Queries fehlschlagen, wird der Lauf `failed`.

Wenn eine Query keine Ergebnisse liefert:

- Query wird als `completed` mit `0` Ergebnissen gespeichert,
- der Lauf setzt normal fort.

### Target-Import-Fehler

Wenn eine URL nicht normalisierbar ist:

- SERP-Result wird `invalid`,
- Fehlergrund wird gespeichert,
- kein Target wird erzeugt.

Wenn die Domain blockiert ist:

- SERP-Result wird `blocked_source`,
- Blockgrund wird gespeichert,
- kein Target wird erzeugt.

Wenn die Source Policy eine Quelle nur als Kontextquelle einordnet:

- SERP-Result wird `review_source`,
- Source-Quality-Metadaten bleiben gespeichert,
- kein primaeres Target wird erzeugt.

### Fetcher-Fehler

Wenn eine Seite nicht erreichbar ist:

- `target_pages.error_message` wird gesetzt,
- HTTP-Status oder technischer Fehler wird gespeichert,
- der Fetcher versucht weitere relevante Seiten,
- bei mindestens einer brauchbaren Seite wird das Target `fetch_partial`,
- bei keiner brauchbaren Seite wird das Target `fetch_failed`.

Targets mit `fetch_failed` gehen nicht automatisch in die DraftEngine. Sie koennen in der Review Queue als technische Prueffaelle sichtbar bleiben oder spaeter erneut gefetcht werden.

### RatingEngine-Fehler

Wenn Rule Scoring nicht genug Kontext hat:

- Target bekommt `rating_failed` oder `rating_partial`,
- empfohlene Aktion ist `review` oder `skip`,
- es wird kein Draft erzeugt.

Wenn AI Scoring fehlschlaegt:

- Rule Score bleibt erhalten,
- AI-Fehler wird gespeichert,
- Target wird `rating_partial`,
- empfohlene Aktion ist maximal `review`,
- kein automatischer Draft.

### DraftEngine-Fehler

Wenn kein valider Draft erzeugt werden kann:

- Score bleibt erhalten,
- Draft-Fehler wird gespeichert,
- Target wird `draft_failed`,
- der Nutzer kann Draft-Erzeugung spaeter erneut starten.

## 12. Batching, Pause und Resume

Request-Budgets machen einen Lauf zu einem Batch.

Die LeadEngine sollte intern mit einer Query-Queue arbeiten:

```text
lead_run
  -> query_queue
  -> executed_queries
  -> remaining_budget
  -> result_groups
```

Minimal fuer V1:

- Lauf synchron starten,
- Fortschritt nach jeder Query und jedem Target speichern,
- bei Fehlern fortsetzen,
- nach Abbruch vorhandene Ergebnisse behalten.

Spaeter:

- `pause`: keine neuen Queries starten, laufenden Schritt beenden.
- `resume`: naechste nicht ausgefuehrte Query oder naechstes offenes Target fortsetzen.
- `cancel`: Lauf stoppen, bestehende Ergebnisse behalten.

Wichtig: Resume darf nicht dieselben Provider-Requests blind wiederholen. Bereits ausgefuehrte Queries muessen gespeichert und dedupliziert werden.

## 13. Rueckpfeile aus der Review Queue

Die Review Queue ist nicht nur das Ende der Pipeline. Sie erzeugt Feedback fuer gezielte Neudurchlaeufe.

Moegliche Nutzeraktionen:

- `approve_draft`: Draft ist fachlich akzeptiert.
- `edit_draft`: Draft wird manuell angepasst.
- `reject_draft`: Draft wird verworfen, Target bleibt erhalten.
- `regenerate_draft`: nur DraftEngine erneut ausfuehren.
- `rerate_target`: RatingEngine erneut ausfuehren, z. B. nach neuem Fetch.
- `refetch_target`: Fetcher erneut ausfuehren.
- `blacklist_target`: Domain blockieren und zukuenftig ausschliessen.
- `update_search_profile`: Suchprofil anpassen und LeadEngine erneut starten.

Rueckpfeile:

```text
Review Queue -> DraftEngine
Review Queue -> RatingEngine
Review Queue -> Fetcher / Extractor
Review Queue -> LeadEngine
Review Queue -> Domain-Denylist
```

Ein abgelehnter Draft startet nicht automatisch einen kompletten neuen LeadEngine-Lauf. Standard ist der kleinste sinnvolle Neudurchlauf:

- Draft schlecht, Score gut: nur DraftEngine.
- Score unplausibel: RatingEngine.
- Seitenkontext schlecht: Fetcher, dann RatingEngine.
- Falsche Target-Art: Denylist oder Suchprofil anpassen, dann LeadEngine.

## Modulgrenzen

```text
LeadEngine  = Finden
RatingEngine = Bewerten
DraftEngine = Formulieren
Pipeline = Orchestrieren
Review Queue = Entscheiden
```

Die Engines sollen sich nicht direkt gegenseitig aufrufen. Die Pipeline verbindet sie ueber Datenbankobjekte und klar definierte Inputs/Outputs.

## Leitentscheidung

Die Pipeline bleibt lokal, nachvollziehbar und human-in-the-loop.

Automatisierung findet nur bis zur Vorbereitung statt. Die finale Entscheidung bleibt immer beim Nutzer.
