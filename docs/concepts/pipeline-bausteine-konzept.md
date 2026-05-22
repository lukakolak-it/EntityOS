# Pipeline-Bausteine Konzept

## Zweck

Dieses Dokument beschreibt die kleineren Bausteine rund um die Engines.

Ausgeschlossen sind:

- LeadEngine
- RatingEngine
- DraftEngine

Beschrieben werden die Komponenten, die Daten vorbereiten, speichern, absichern, nachverfolgbar machen und menschliche Entscheidungen ermoeglichen.

## Einordnung

```text
Profil + Suchprofil
  -> LeadEngine
  -> Target Import
  -> Fetcher / Extractor
  -> RatingEngine
  -> DraftEngine
  -> Review Queue
  -> Entscheidung / Ruecklauf
```

Die Engines erledigen die fachlich grossen Aufgaben. Die Pipeline-Bausteine sorgen dafuer, dass diese Aufgaben kontrolliert, nachvollziehbar und wiederholbar ablaufen.

## 1. Profil

Das Profil beschreibt die suchende oder anbietende Seite.

Im Bewerbungs-Preset ist das ein Bewerberprofil. In spaeteren Presets kann es ein Anbieterprofil, Produktprofil oder Opportunity-Profil sein.

Aufgaben:

- Stammdaten halten
- Skills und fachliche Signale bereitstellen
- Zielrolle oder Opportunity-Typ beschreiben
- Sprache, Standort, Remote-Wunsch und Verfuegbarkeit speichern
- Draft- und Rating-Kontext liefern

Das Profil startet keine Verarbeitung. Es ist reiner Kontext.

## 2. Suchprofil

Das Suchprofil ist die konkrete Suchabsicht fuer einen Lauf.

Aufgaben:

- Rollen- oder Zielbegriffe speichern
- Regionen speichern
- Tech- und Branchenbegriffe speichern
- Ausschlussbegriffe speichern
- optional manuelle Query speichern
- LeadEngine- und Rating-Kontext liefern

Ein Profil kann mehrere Suchprofile haben.

Beispiel:

```text
Profil: Informatikstudentin B.Sc.
Suchprofil: Werkstudentin IT Essen / Hybrid
```

## 3. Target Import

Der Target Import ist die Schleuse zwischen gefundenen URLs und lokalen Targets.

Aufgaben:

- URLs normalisieren
- Domain extrahieren
- Dubletten erkennen
- bestehende Targets wiederverwenden
- Quelle speichern, z. B. `manual`, `csv`, `serp:brave`
- blockierte Domains abweisen
- Import-Ergebnis je URL nachvollziehbar speichern

Der Target Import bewertet nicht, ob ein Target fachlich passt.

Moegliche Importstatus:

- `imported`
- `existing`
- `duplicate_input`
- `review_source`
- `blocked_source`
- `blacklisted`
- `invalid`

Abgrenzung:

- `duplicate_input`: dieselbe URL oder normalisierte Domain kommt mehrfach im selben Import-Payload vor.
- `review_source`: die Quelle ist eine Kontextquelle, z. B. Verzeichnis, Register oder News, und wird nicht als primaeres Target importiert.
- `blocked_source`: die Domain ist durch eine systemische Denylist oder Source-Regel blockiert, z. B. Jobboerse oder Aggregator.
- `blacklisted`: die Domain wurde durch eine Nutzerentscheidung ausgeschlossen und soll auch in kuenftigen Laeufen nicht importiert werden.
- `existing`: das Target existiert bereits lokal und wird wiederverwendet.
- `invalid`: URL oder Domain kann nicht sinnvoll normalisiert werden.

`duplicate_domain` ist kein Target-Importstatus, sondern ein LeadEngine-Status fuer SERP-Ergebnisse innerhalb eines Discovery-Laufs. Wenn der deduplizierte Kandidat an den Target Import uebergeben wird, wird daraus je nach lokaler Lage `imported`, `existing`, `review_source`, `blocked_source`, `blacklisted` oder `invalid`.

## 4. Target

Ein Target ist die lokale, normalisierte Arbeitseinheit.

Im Bewerbungs-Preset ist ein Target meist eine Firma oder Organisation. In anderen Presets kann es ein Lead, Anbieter, Kunde, Projektgeber oder sonstiges Zielobjekt sein.

Aufgaben:

- Domain und Basis-URL halten
- Quelle und Status halten
- Pages, Scores und Drafts verbinden
- Blacklist- und Review-Entscheidungen tragen

Das Target ist der zentrale Anker nach der Discovery.

## 5. Fetcher

Der Fetcher sammelt wenige relevante Seiten eines Targets.

Aufgaben:

- Homepage laden
- relevante interne Links erkennen
- begrenzte Anzahl Unterseiten laden
- HTTP-Status, Fehler und Zeitpunkte speichern
- Robots-/Timeout-/Netzwerkfehler isolieren

Der Fetcher ist kein breiter Crawler.

V1-Regel:

```text
wenige Seiten pro Domain, lokal nachvollziehbar, keine unkontrollierte Tiefensuche
```

Moegliche Fetchstatus:

- `fetch_pending`
- `fetch_partial`
- `fetch_failed`
- `fetched`

## 6. Extractor

Der Extractor verarbeitet geladene Seiten.

Aufgaben:

- sichtbaren Text extrahieren
- Titel extrahieren
- Kontakt-E-Mails extrahieren
- interne und externe Links extrahieren
- Seitentyp grob markieren, z. B. Homepage, Karriere, Kontakt

Der Extractor soll keine fachliche Bewertung machen. Er bereitet Text und Signale fuer Rating und Drafts vor.

## 7. Pages

Target Pages sind gespeicherte Seitenkontexte.

Aufgaben:

- URL speichern
- Seitentyp speichern
- HTTP-Status speichern
- extrahierten Text speichern
- extrahierte Kontakte und Links speichern
- Fehler speichern

Pages sind die wichtigste Evidenzquelle fuer RatingEngine und DraftEngine.

## 8. Denylist und Blacklist

Denylist und Blacklist verhindern schlechte oder unerwuenschte Targets.

Unterscheidung:

- Denylist: Quellen- und Domainfilter fuer Discovery, z. B. Jobportale.
- Blacklist: Nutzerentscheidung gegen eine konkrete Domain.

Aufgaben:

- bekannte Jobportale blockieren
- Recruiting- und Meta-Portale blockieren
- manuell verworfene Domains speichern
- zukuenftige Imports verhindern
- Review-Feedback in die Discovery zurueckspielen

Beispiele:

```text
stepstone.de
indeed.com
de.jooble.org
xing.com
kimeta.de
```

## 9. Pipeline Run

Ein Pipeline Run ist die Laufklammer fuer eine Verarbeitung.

Aufgaben:

- Start- und Endzeit speichern
- Status speichern
- Modus speichern
- Zaehler speichern
- Fehler und Teilfehler speichern
- betroffene Targets nachvollziehbar machen

Moegliche Status:

- `pending`
- `running`
- `paused`
- `completed`
- `completed_with_errors`
- `failed`
- `cancelled`

Ein einzelner Target-Fehler soll den Lauf nicht automatisch abbrechen.

## 10. Statusmodell

Das Statusmodell macht den Fortschritt pro Target sichtbar.

Beispiele:

- `candidate`
- `blocked_source`
- `imported`
- `existing`
- `fetch_pending`
- `fetch_partial`
- `fetch_failed`
- `rating_pending`
- `rating_partial`
- `rating_failed`
- `draft_pending`
- `draft_failed`
- `needs_review`
- `rejected`
- `approved`
- `blacklisted`

Status sind Produktlogik. Sie muessen in API und UI gleich verstanden werden.

### Aktueller Status vs. Status-Historie

MVP-Entscheidung:

- `targets.status` bleibt der aktuelle Arbeitszustand.
- Statuswechsel duerfen den aktuellen Zustand ueberschreiben.
- Zusaetzlich soll eine append-only Historie eingefuehrt werden: `target_status_log`.

Grund:

Ein Target kann z. B. erst `fetch_failed` sein, spaeter manuell neu gefetcht werden und danach `fetched` oder `needs_review` erreichen. Der aktuelle Status soll dann den neuesten Zustand zeigen. Fuer Debugging, Vertrauen und Produktmetriken muss der alte Fehler aber erhalten bleiben.

### Tabelle `target_status_log`

MVP-Spalten:

- `id`
- `target_id`
- `pipeline_run_id` nullable
- `from_status`
- `to_status`
- `phase`
- `reason`
- `error_message`
- `metadata_json`
- `created_at`

Beispiele fuer `phase`:

- `import`
- `fetch`
- `extract`
- `rating`
- `draft`
- `review`
- `reprocess`

Regel:

```text
Jede automatische Statusaenderung und jede Nutzerentscheidung schreibt einen Logeintrag.
```

`pipeline_run_id` ist nullable.

Regel fuer die Zuordnung:

- Statuswechsel innerhalb eines Pipeline Runs setzen `pipeline_run_id`.
- Einzelne API-Aktionen wie `POST /targets/{id}/rerate`, `POST /targets/{id}/refetch` oder Nutzerentscheidungen duerfen `pipeline_run_id = NULL` schreiben.
- In diesem Fall dokumentiert `metadata_json` mindestens den Trigger, z. B. `api_rerate`, `api_refetch`, `review_action`, den Endpoint und relevante Request-Parameter.
- Wenn eine Einzelaktion spaeter als laenger laufender, beobachtbarer Reprocessing-Lauf umgesetzt wird, darf sie intern einen Pipeline Run mit passendem Scope erzeugen und dann dessen ID setzen.

Die UI zeigt standardmaessig nur den aktuellen Status. In der Target-Detailansicht kann die Status-Historie aufgeklappt werden.

## 11. Review Queue

Die Review Queue ist der menschliche Kontrollpunkt.

Aufgaben:

- Targets und Drafts pruefbar machen
- Scores, Gruende und Risiken anzeigen
- Quellen sichtbar machen
- Drafts bearbeiten lassen
- Targets verwerfen oder freigeben
- Domains blacklisten
- gezielte Neudurchlaeufe starten

Die Review Queue ist kein Endpunkt ohne Rueckweg. Sie ist der Ort, an dem Nutzerfeedback in das System zurueckfliesst.

### Skalierung und Priorisierung

Die Review Queue muss auch mit 100-200 offenen Targets nutzbar bleiben.

MVP-Entscheidung:

- serverseitige Pagination
- Default-Sortierung nach Score absteigend, dann Aktualitaet absteigend
- Filter nach Status, Suchprofil, Quelle und Risiko
- Bulk-Auswahl fuer einfache Aktionen

Default-Sortierung:

```text
recommended_action = draft zuerst
ai_score absteigend
confidence absteigend
updated_at absteigend
```

Weitere Sortierungen:

- neueste zuerst
- hoechster Score zuerst
- niedrigstes Risiko zuerst
- Quelle / Provider
- Suchprofil

Bulk-Aktionen im MVP:

- selected targets blacklisten
- selected targets verwerfen
- selected targets refetch
- selected targets rerate

Bulk-Draft-Regeneration bleibt spaeter, damit nicht versehentlich viele Drafts neu erzeugt werden.

## 12. Reprocessing

Reprocessing bedeutet: nicht die ganze Pipeline neu starten, sondern den kleinsten sinnvollen Schritt wiederholen.

Regeln:

- Draft schlecht, Score gut: nur Draft neu erzeugen.
- Score unplausibel: Rating erneut ausfuehren.
- Seitenkontext schlecht: Fetch erneut ausfuehren, danach Rating.
- Target-Art falsch: Domain blockieren oder Suchprofil anpassen.
- Discovery schlecht: LeadEngine mit anderem Template-Set oder Budget erneut starten.

Moegliche Aktionen:

- `regenerate_draft`
- `rerate_target`
- `refetch_target`
- `blacklist_target`
- `update_search_profile`
- `rerun_discovery`

### UI-Trigger

Reprocessing wird in der UI explizit ausgeloest.

Target-Detailansicht:

- Button `Refetch`
- Button `Rerate`
- Button `Regenerate Draft`
- Button `Blacklist Domain`
- Button `Reject`
- Button `Approve`

Review Queue Listenansicht:

- Zeilenaktion `Refetch`
- Zeilenaktion `Rerate`
- Zeilenaktion `Regenerate Draft`
- Zeilenaktion `Blacklist`
- Bulk-Aktion `Refetch selected`
- Bulk-Aktion `Rerate selected`
- Bulk-Aktion `Blacklist selected`

Suchprofilansicht:

- Button `Run Discovery`
- Button `Refresh Discovery`
- Button `Run Pipeline`

Regel:

```text
Die UI startet immer den kleinsten sinnvollen Neudurchlauf und zeigt vorher an, welche Phase erneut ausgefuehrt wird.
```

## 13. Fehler- und Evidenzspeicherung

Jeder Baustein speichert Fehler dort, wo sie entstehen.

Beispiele:

- Import speichert ungueltige URLs.
- Fetcher speichert HTTP- und Netzwerkfehler.
- Extractor speichert leere oder nicht parsebare Inhalte.
- Rating speichert Teilfehler ueber Scores.
- Draft-Erzeugung speichert Validierungsfehler.

Grundregel:

```text
Fehler sollen sichtbar und lokal behebbar sein, nicht still verschwinden.
```

## 14. API-Sicht

Die Bausteine sollten ueber klare, kleine API-Grenzen sichtbar sein.

Beispiele:

```text
GET  /profiles
GET  /search-profiles
POST /imports/urls
GET  /targets
GET  /targets/{id}/pages
GET  /targets/{id}/scores
GET  /targets/{id}/status-log
GET  /drafts
GET  /pipeline-runs
POST /pipeline-runs
GET  /pipeline-runs/{id}
POST /pipeline-runs/{id}/pause
POST /pipeline-runs/{id}/resume
POST /pipeline-runs/{id}/cancel
POST /targets/{id}/blacklist
POST /targets/{id}/refetch
POST /targets/{id}/rerate
POST /drafts/{id}/regenerate
```

Die API sollte nicht alle Engines direkt nach aussen leaken. Fuer Nutzer sind Targets, Runs, Drafts und Review-Aktionen wichtiger als interne Engine-Namen.

### Laufstart per API

`POST /pipeline-runs` startet einen neuen orchestrierten Lauf.

Beispiel:

```json
{
  "search_profile_id": 3,
  "mode": "focused",
  "phases": ["lead", "fetch", "rate", "draft"],
  "request_budget": 100,
  "results_per_query": 10,
  "auto_import": false
}
```

`phases` erlaubt gezielte Laeufe:

- `["lead"]`: nur Discovery
- `["fetch"]`: nur Fetch fuer bestehende Targets
- `["rate"]`: nur Rating
- `["draft"]`: nur Draft-Erzeugung
- `["fetch", "rate"]`: Refetch und Neubewertung
- `["lead", "fetch", "rate", "draft"]`: kompletter Lauf

Fuer einzelne Target-Aktionen bleiben die spezifischen Endpoints besser als ein generischer Pipeline-Run.

## 15. UI-Sicht

Die UI sollte diese Bausteine als Arbeitsfluss zeigen:

- Profil und Suchprofil konfigurieren
- Discovery/Import-Ergebnisse pruefen
- Target-Details mit Pages ansehen
- Scores und Quellen nachvollziehen
- Drafts in der Review Queue bearbeiten
- Fehler und blockierte Domains verwalten
- gezielte Neudurchlaeufe starten

Konkrete UI-Entscheidungen:

- Review Queue als paginierte Tabelle mit Filterleiste.
- Target-Detailansicht mit Actions-Bar fuer `Refetch`, `Rerate`, `Regenerate Draft`, `Blacklist`, `Reject`, `Approve`.
- Status-Historie in der Target-Detailansicht als einklappbarer Verlauf.
- Pipeline Runs als eigene Ansicht mit Status, Zaehlern, Fehlern und betroffenen Targets.
- Suchprofilseite mit `Run Discovery`, `Refresh Discovery` und `Run Pipeline`.

Wichtig:

- Jede Entscheidung muss nachvollziehbar sein.
- Jeder Fehler muss einen naechsten sinnvollen Schritt haben.
- Automatisierung endet vor der finalen Nutzerentscheidung.

## 16. MVP-Prioritaet

Fuer den MVP sind diese Bausteine kritisch:

- Profil
- Suchprofil
- Target Import
- Target
- Fetcher
- Extractor
- Pages
- Denylist / Blacklist
- Pipeline Run
- Review Queue

Spaeter ausbaubar:

- feingranulares Statusmodell pro Lauf-Target
- Pause/Resume
- explizite Reprocessing-API
- bessere UI fuer technische Teilfehler
- Audit Log fuer Nutzerentscheidungen

## Leitentscheidung

Die Engines liefern die fachliche Automatisierung. Die Pipeline-Bausteine liefern Kontrolle, Persistenz und Nachvollziehbarkeit.

Ohne diese Bausteine waere Target Radar nur eine Abfolge von Skripten. Mit ihnen wird es ein lokales, pruefbares Produkt.
