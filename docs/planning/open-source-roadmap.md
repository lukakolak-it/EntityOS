# Open-Source-Roadmap

Dieses Dokument beschreibt den Weg vom aktuellen lokalen MVP zu einem
nuetzlichen Open-Source-Tool.

Ausgangspunkt:

- lokale UI laeuft auf `127.0.0.1`
- Brave Search und Ollama-Light-Routing sind integriert
- Sprints 0 bis 15 aus `sprints-und-slices.md` sind umgesetzt
- Engine-Evaluation ist vorhanden
- Research-Summary-Drafts sind grounded und reviewbar

Ziel ist kein hosted SaaS, sondern ein lokal installierbares Werkzeug fuer
konfigurierbare OSINT- und Research-Workflows.

## Definition: nuetzliches Open-Source-Tool

Ein erster brauchbarer Open-Source-Release ist erreicht, wenn ein technisch
versierter Nutzer lokal:

1. das Projekt installieren und starten kann,
2. Secrets und Provider ohne Codeaenderung konfigurieren kann,
3. einen mitgelieferten OSINT-Use-Case ausfuehren kann,
4. Ergebnisse in der UI pruefen, bewerten und exportieren kann,
5. eigene einfache Use Cases ueber die UI erstellen kann,
6. Daten lokal behalten und nachvollziehbar loeschen kann,
7. Fehler diagnostizieren kann, ohne Python-Code lesen zu muessen.

Nicht Ziel fuer den ersten Open-Source-Release:

- Multi-User-Betrieb
- Cloud-Hosting
- automatische Kontaktaufnahme
- vollstaendiges Plugin-System mit beliebigem Code
- perfekte Trefferqualitaet fuer alle Branchen

## Release-Ziel

Empfohlenes Ziel: `v0.1.0-local-osint`.

Release-Qualitaet:

- Installation und erster Lauf sind dokumentiert.
- Alle Tests und Eval-Suites laufen lokal gruen.
- Ein Demo-Use-Case funktioniert ohne echte Secrets mit Mock-Daten.
- Ein echter Use Case funktioniert mit Brave + Ollama.
- README, Datenschutzhinweise und Troubleshooting sind aktuell.

## Sprint 16: Echte Pilotdaten und Feedback-Loop

Ziel:

Die Engine-Verbesserung soll ab jetzt gegen echte lokale Review-Entscheidungen
laufen, nicht gegen Bauchgefuehl.

Status:

- Sprint-16-Infrastruktur ist umgesetzt.
- Ein lokaler Referenzlauf wurde als Run `#26` ausgefuehrt.
- `export-run-report` erzeugt einen lokalen Run-Report mit Queries, Targets,
  Review-Backlog und Review-Feedback-Triage.
- Die echte manuelle Review-Runde bleibt bewusst ein Human-in-the-loop-Schritt
  und wird nicht automatisch simuliert.

### Slice 16.1: Neuer Referenzlauf

Status: umgesetzt fuer den aktuellen lokalen Pilotlauf.

Umfang:

- kleinen echten OSINT-Run mit Light-LLM ausfuehren
- Run-ID, Zeit, Query-Parameter und Use Case dokumentieren
- erzeugte Targets, Ratings und Drafts pruefen

Akzeptanzkriterien:

- ein aktueller Run ist in der lokalen DB vorhanden
- Review Queue enthaelt pruefbare Ergebnisse
- Provider-Status und Run-Parameter sind nachvollziehbar

### Slice 16.2: Manuelle Review-Runde

Status: offen fuer Nutzer-Review in der UI.

Umfang:

- Ergebnisse in der UI konsequent markieren
- passende Targets approven
- unpassende Targets rejecten oder blacklisten
- unklare Targets als Kontextproblem markieren

Akzeptanzkriterien:

- mindestens 20 Targets wurden manuell bewertet oder bewusst ausgelassen
- Review-Entscheidungen sind exportierbar
- typische Fehlertypen sind erkennbar

### Slice 16.3: Review-Feedback als Eval-Fixture

Status: umgesetzt als `export-review-eval`, `evaluate --fixture` und
`export-run-report`.

Umfang:

- Review-Feedback exportieren
- Konflikte zwischen Nutzerentscheidung und Engine-Entscheidung triagieren
- harte Fehlfaelle in Eval-Fixtures uebernehmen

Akzeptanzkriterien:

- Review-Eval laeuft reproduzierbar
- neue Fixture-Faelle decken echte Fehlentscheidungen ab
- Triage-Ausgabe nennt konkrete naechste Engine-Fixes

### Slice 16.4: Erste Fix-Runde aus echten Fehlfaellen

Status: umgesetzt fuer die erste Run-26-Review-Runde.

Umgesetzte Fixes:

- Homepage-URLs werden nicht mehr nur wegen Navigationslinks wie `Karriere`
  als Career-Seiten klassifiziert.
- Platzhalterseiten wie `Diese Domain ist unkonfiguriert` werden als
  unbrauchbare Evidence erkannt und auf `skip` gesetzt.
- Rating-Grounding akzeptiert belegte Zitate auch dann, wenn das LLM auf
  derselben Domain einen leicht abweichenden Pfad nennt oder ein Zitat mit
  Ellipsen kuerzt. Der Quote-Text muss weiterhin in gespeicherter Evidence
  belegbar sein.
- LLM-Rating normalisiert Label-, Prozent- und Kleinskalenwerte wie `high`,
  `88/100`, `76%` oder `4/5` robust, statt daraus `ai_provider_error` oder
  falsch niedrige Scores zu machen. String-Reasons werden deterministisch an
  passende Context-Evidence gebunden.
- Hybrid-Kriterien blockieren nur noch wegen fehlender AI-Evidence, wenn der
  AI-Score den Rule-Score fuer das Kriterium tatsaechlich anhebt.
- Eval-Baseline enthaelt Regressionen fuer die Run-26-Faelle
  `borowski.de`, `wattmacher.nrw` und `brenner-energie.de`.

Umfang:

- Top-3-Konflikte aus der Triage beheben
- Source-Quality-, Topic-Fit-, Evidence- oder Rating-Regeln gezielt anpassen
- Eval-Suite erweitern

Akzeptanzkriterien:

- geloeste Fehlfaelle bleiben als Regressionstests erhalten
- keine Verschlechterung der bestehenden Eval-Suite
- die naechste Triage-Liste ist kuerzer oder klarer

## Sprint 17: Use-Case-Builder MVP

Status: umgesetzt als lokales MVP.

Ziel:

Nutzer sollen einfache eigene Use Cases ohne JSON- oder Codebearbeitung
erstellen koennen.

### Slice 17.1: Use-Case-Liste und Detailseite

Status: umgesetzt.

Umfang:

- vorhandene Use Cases anzeigen
- aktive, mitgelieferte und lokale Use Cases unterscheiden
- JSON-Rohansicht als Debug-Hilfe behalten

Akzeptanzkriterien:

- Nutzer erkennt, welcher Use Case fuer Runs genutzt wird
- mitgelieferte Templates sind nicht versehentlich editierbar
- lokale Kopien koennen erstellt werden

### Slice 17.2: Formular fuer Attribute und Query Policy

Status: umgesetzt.

Umfang:

- Attribute mit Key, Label, Typ und Pflichtstatus bearbeiten
- Query-Templates validieren
- Template-Variablen gegen Attribute pruefen

Akzeptanzkriterien:

- ungueltige Template-Variablen werden blockiert
- Preview zeigt generierte Queries
- ein einfacher eigener Use Case erzeugt valide Run-Eingaben

### Slice 17.3: Source Policy Editor

Status: umgesetzt.

Umfang:

- preferred, context und blocked source types pflegen
- relevante Pfad-Tokens konfigurieren
- lokale Domain-Policies verknuepfen

Akzeptanzkriterien:

- Source Policy ist ohne JSON editierbar
- ungueltige Source Types werden klar gemeldet
- Query- und Source-Preview nutzt die Policy

### Slice 17.4: Rating- und Draft-Policy Editor

Status: umgesetzt.

Umfang:

- Kriterien, Gewichte und Mindest-Evidence bearbeiten
- Gewichtssumme exakt 100 validieren
- Draft-Typ, Pflichtabschnitte und verbotene Phrasen pflegen

Akzeptanzkriterien:

- bekannte Kriterien nutzen vorhandene Rule-Sets
- Custom-Kriterien werden als LLM-gestuetzt gekennzeichnet
- ungueltige Draft-Policies werden vor dem Speichern blockiert

### Slice 17.5: Import, Export und Template-Kopien

Status: umgesetzt.

Umfang:

- Use Case als Datei exportieren
- Use Case aus Datei importieren
- Namenskonflikte sicher behandeln

Akzeptanzkriterien:

- exportierte Use Cases enthalten keine Secrets
- Import ueberschreibt nichts ohne explizite Entscheidung
- Beispiel-Use-Case laesst sich importieren und ausfuehren

## Sprint 18: OSINT-Kern generalisieren

Status: umgesetzt.

Ziel:

Das System soll nicht mehr nach Jobportal-Logik riechen, sondern als
allgemeines lokales Research-Werkzeug funktionieren.

### Slice 18.1: Neutrale Source-Type-Taxonomie

Status: umgesetzt.

Umfang:

- Source Types fuer Registry, Directory, News, Repository, Social, Official Site
  und Search Result vereinheitlichen
- alte jobbezogene Begriffe nur im Bewerbungs-Use-Case belassen
- Klassifizierungsregeln dokumentieren
- `search_result` als eigener Source Type fuer Suchmaschinen-/SERP-Seiten
  ergaenzt
- `job_board` bleibt fuer den Bewerbungs-Use-Case erhalten, ist aber kein
  OSINT-Leitbegriff mehr

Akzeptanzkriterien:

- OSINT-Use-Cases koennen ohne Job-Wording konfiguriert werden
- bestehender Bewerbungs-Use-Case bleibt lauffaehig
- Source-Quality-Eval deckt die wichtigsten Source Types ab

### Slice 18.2: Query Packs

Status: umgesetzt.

Umfang:

- query packs fuer Company OSINT, Open-Source-Projekte und Vendor Research
  definieren
- Query-Budget pro Pack steuerbar machen
- Preview fuer Pack-Auswahl anzeigen
- Use Cases koennen `query_packs` mit eigenem `request_budget` definieren
- `company_osint` liefert Packs fuer Company OSINT, Open-Source-Projekte und
  Vendor Research

Akzeptanzkriterien:

- ein Use Case kann mehrere Query Packs nutzen
- Nutzer sieht vor dem Run, welche Query-Familien laufen
- Eval-Faelle decken Query-Erwartungen ab

### Slice 18.3: Evidence-Type-Ausbau

Status: umgesetzt.

Umfang:

- Evidence Types fuer `identity`, `activity`, `reputation`, `contact`,
  `official_claim`, `third_party_claim` einfuehren
- Extractor- und EvidenceEngine-Mapping erweitern
- UI-Evidence-Karten danach gruppieren
- Legacy-`evidence_type` bleibt fuer Rueckwaertskompatibilitaet erhalten
- neue `evidence_category` unterscheidet Eigenangabe, Drittquelle, Identitaet,
  Aktivitaet, Reputation und Kontakt

Akzeptanzkriterien:

- Research Summary unterscheidet Eigenangabe und Drittquelle
- Rating kann Kriterien an Evidence Types binden
- Review UI zeigt Evidence-Herkunft klarer

### Slice 18.4: Research-Summary-Varianten

Status: umgesetzt.

Umfang:

- Draft-Varianten fuer `company_summary`, `project_summary`,
  `vendor_risk_note` definieren
- Pflichtabschnitte und verbotene Aussagen je Variante konfigurieren
- Validierung wiederverwenden
- `research_summary`, `company_summary`, `project_summary` und
  `vendor_risk_note` teilen Grounding- und Section-Validierung

Akzeptanzkriterien:

- mindestens zwei OSINT-Draft-Typen funktionieren
- beide bleiben strikt evidence-grounded
- UI zeigt Draft-Typ und Grounding konsistent

## Sprint 19: Installation, Migration und lokale Diagnose

Ziel:

Ein externer Nutzer soll das Projekt ohne persoenliche Einweisung starten
koennen.

### Slice 19.1: Setup-Pfad vereinfachen

Umfang:

- README auf aktuellen Stand bringen
- `.env.example` vollstaendig dokumentieren
- Setup-Schritte fuer Windows und Unix beschreiben

Akzeptanzkriterien:

- frischer Clone kann nach README gestartet werden
- alle benoetigten Provider-Variablen sind beschrieben
- Mock-Modus funktioniert ohne Secrets

### Slice 19.2: Preflight-Diagnose

Umfang:

- Diagnose fuer Python-Version, DB, Schreibrechte, Brave, Ollama und Modelle
- UI-Seite fuer Provider- und Systemstatus ausbauen
- klare Fehlertexte mit naechstem Schritt

Akzeptanzkriterien:

- fehlender Ollama-Dienst wird eindeutig angezeigt
- fehlender Brave-Key blockiert nur echte Suche, nicht Mock-Modus
- Diagnose kann fuer Bugreports kopiert werden

### Slice 19.3: Datenbankmigrationen und Backup

Umfang:

- lokale Migrationsstrategie fuer SQLite festlegen
- Backup vor Migration anbieten
- Schema-Version sichtbar machen

Akzeptanzkriterien:

- bestehende lokale DB kann aktualisiert werden
- fehlgeschlagene Migration zerstoert keine Daten
- Diagnose zeigt Schema-Version und Migrationsstatus

### Slice 19.4: Lokale Datenverwaltung

Umfang:

- UI-Aktion fuer Run-Daten loeschen
- Export vor Loeschung anbieten
- Secrets nie exportieren

Akzeptanzkriterien:

- Nutzer kann Testdaten gezielt entfernen
- Datenschutz-Check bleibt gruen
- Loeschaktionen werden lokal protokolliert

## Sprint 20: UI fuer taegliche Nutzung

Ziel:

Die UI soll nicht nur technisch funktionieren, sondern wiederholte Review-Arbeit
angenehm machen.

### Slice 20.1: Dashboard

Umfang:

- letzte Runs, offene Reviews, Fehler und Providerstatus zusammenfassen
- Schnellaktionen fuer neuen Run und Review Queue
- aktive Use Cases sichtbar machen

Akzeptanzkriterien:

- Nutzer sieht nach dem Start den naechsten sinnvollen Schritt
- Fehler sind direkt erreichbar
- keine Marketing-Startseite

### Slice 20.2: Review Queue Filter und Bulk-Aktionen

Umfang:

- Filter nach Use Case, Run, Status, Action, Source Type und Risiko
- Bulk-Aktionen fuer offensichtliche Rejects oder Blacklist
- Review-Entscheidungen rueckgaengig machen

Akzeptanzkriterien:

- 100-200 offene Targets bleiben bearbeitbar
- Bulk-Aktionen sind bestaetigungspflichtig
- Feedback-Export beruecksichtigt Bulk-Entscheidungen

### Slice 20.3: Target Detail Politur

Umfang:

- Timeline aus Run, Fetch, Rating, Draft und Review
- Evidence, Rating-Gruende und Draft nebeneinander besser verknuepfen
- direkte Reprocess-Aktionen klarer machen

Akzeptanzkriterien:

- ein Target kann ohne Datenbankblick nachvollzogen werden
- Draft-Grounding und Evidence sind schnell pruefbar
- Fehlerlogs sind lesbar, aber nicht dominant

### Slice 20.4: UI-Smoke- und Regressionstests

Umfang:

- Playwright-Smoke fuer Startseite, Run, Review, Target Detail, Use Cases und
  Secrets
- Screenshot-Checks fuer Kernseiten
- stabile Testdaten verwenden

Akzeptanzkriterien:

- UI-Regressionssuite laeuft lokal
- Kernseiten sind nicht leer und nicht kaputt gerendert
- Tests sind ohne echte Provider-Secrets ausfuehrbar

## Sprint 21: Qualitaets-Gates und Release-Haerte

Ziel:

Vor dem Open-Source-Release muss klar sein, was bei Aenderungen nicht brechen
darf.

### Slice 21.1: Eval-Goldset erweitern

Umfang:

- echte, anonymisierte oder synthetisierte Faelle fuer Source Quality, Rating,
  Draft und Use Cases sammeln
- erwartete Aktionen festlegen
- bekannte Grenzfaelle dokumentieren

Akzeptanzkriterien:

- Eval-Suite hat mindestens 50 Faelle
- jeder Fehler nennt Section, Case-ID und erwartete Aktion
- neue Engine-Fixes starten mit einem Eval-Fall

### Slice 21.2: CI-Basis

Umfang:

- GitHub Actions fuer Tests, Compile, Eval und Datenschutz-Check
- keine Secrets fuer Standard-CI noetig
- optionaler Provider-Test bleibt lokal

Akzeptanzkriterien:

- Pull Requests sehen schnell, ob Grundfunktionen brechen
- Eval-Suite ist Teil des Standard-Gates
- CI laeuft ohne lokale Daten

### Slice 21.3: Performance- und Budgetgrenzen

Umfang:

- Run-Budget, Query-Budget, Fetch-Limits und LLM-Timeouts dokumentieren
- UI zeigt geschaetzte Kosten/Risiken pro Run
- harte Limits gegen versehentliche grosse Runs

Akzeptanzkriterien:

- Nutzer kann keinen unbegrenzten Provider-Run versehentlich starten
- Timeouts fuehren zu reviewbaren Fehlern
- lokale Logs zeigen Budgetverbrauch

### Slice 21.4: Security- und Privacy-Review

Umfang:

- Secrets-Seite pruefen
- Exportformate auf Secret-Leaks testen
- lokale Datenpfade und `.gitignore` validieren
- Security Policy schreiben

Akzeptanzkriterien:

- Datenschutz-Check deckt typische Leaks ab
- README erklaert lokale Datenhaltung
- Bugreports sollen keine Secrets enthalten muessen

## Sprint 22: Open-Source-Release

Ziel:

Das Projekt soll fuer erste externe Nutzer verstaendlich, installierbar und
beitragbar sein.

### Slice 22.1: Projekt-Metadaten

Umfang:

- Lizenz finalisieren
- `CONTRIBUTING.md`, `SECURITY.md`, Issue-Templates und Code of Conduct
- Support-Grenzen und Nicht-Ziele dokumentieren

Akzeptanzkriterien:

- Repository ist als Open-Source-Projekt verstaendlich
- Sicherheitsmeldungen haben einen klaren Pfad
- Mitwirkende finden Setup und Testbefehle

### Slice 22.2: Beispielpaket

Umfang:

- Demo-Daten ohne echte Personen oder Secrets
- Beispiel-Use-Cases fuer Company OSINT und Open-Source-Projekte
- kurze Walkthrough-Doku

Akzeptanzkriterien:

- neuer Nutzer kann eine Demo ohne Provider starten
- echter Brave/Ollama-Lauf ist der zweite Schritt, nicht Voraussetzung
- Screenshots oder kurze UI-Beschreibung sind aktuell

### Slice 22.3: Release-Kandidat

Umfang:

- Version setzen
- Changelog schreiben
- Tests, Eval, UI-Smoke, Datenschutz-Check ausfuehren
- bekannte Limitationen dokumentieren

Akzeptanzkriterien:

- `v0.1.0-local-osint` kann getaggt werden
- offene Risiken stehen in den Release Notes
- Installation wurde in einem frischen Clone geprueft

### Slice 22.4: Feedback-Kanal fuer externe Nutzer

Umfang:

- Issue-Labels fuer Bug, Eval Case, Use Case, Provider, Docs
- Vorlage fuer anonymisierte Fehlfaelle
- Roadmap nach `v0.1.0` pflegen

Akzeptanzkriterien:

- Nutzer koennen schlechte Treffer als reproduzierbare Eval-Faelle melden
- neue Use-Case-Ideen haben ein klares Format
- naechste Prioritaeten sind sichtbar

## Empfohlene Reihenfolge ab jetzt

1. Sprint 16 durchziehen und echte Fehlfaelle sammeln.
2. Danach Sprint 17 bauen, weil eigene Use Cases der groesste Open-Source-Hebel
   sind.
3. Sprint 19 teilweise parallel vorziehen, sobald ein externer Nutzer testen
   soll.
4. Sprint 18 und 20 iterativ mit echten Review-Daten verbessern.
5. Sprint 21 und 22 erst starten, wenn ein fremder Nutzer den Basis-Flow
   erfolgreich lokal ausfuehren kann.

## Grobe Restgroesse

Bis zu einem nuetzlichen lokalen Open-Source-Tool fehlen ab aktuellem Stand
ungefaehr:

- 2 bis 3 Sprints fuer echten Nutzen ausserhalb des eigenen Rechners
- 4 bis 5 Sprints fuer einen belastbaren `v0.1.0`-Release
- weitere Sprints fuer breitere OSINT-Use-Cases und Plugin-artige Erweiterung

Der kritischste Pfad ist nicht mehr die Grundarchitektur, sondern:

```text
echte Review-Daten -> Eval-Faelle -> Engine-Fixes -> bessere Use-Case-UI -> installierbarer Release
```
