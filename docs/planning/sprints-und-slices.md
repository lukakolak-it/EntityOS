# Sprints und Slices

## Zweck

Dieses Dokument zerlegt Target Radar in umsetzbare Sprints und vertikale Slices.

Ein Sprint ist ein Arbeitsabschnitt mit einem klaren Ziel. Ein Slice ist ein kleiner, testbarer Produktfortschritt innerhalb eines Sprints. Slices sollen nach Moeglichkeit nicht nur technische Schichten liefern, sondern sichtbares Verhalten oder belastbare Grundlage fuer das naechste Verhalten.

## Leitplanken

- MVP bleibt local-first.
- Es gibt keinen automatischen Versand.
- Nutzer pruefen Drafts und finale Entscheidungen manuell.
- `.env`, lokale Datenbanken, Logs, echte Profile und Exporte bleiben ausserhalb von Git.
- LeadEngine, RatingEngine und DraftEngine bleiben getrennte fachliche Module.
- Pipeline oder API-Service schreiben Statuswechsel und Status-Historie.
- Ratings und Drafts werden versioniert und nicht blind ueberschrieben.

## Slice-Definition of Done

Ein Slice gilt als fertig, wenn:

- das Zielverhalten implementiert oder dokumentiert ist,
- relevante Tests vorhanden sind,
- lokale Secrets und Laufzeitdaten nicht versioniert werden,
- Status- und Fehlerverhalten nachvollziehbar ist,
- README oder Konzeptdokumente angepasst sind, wenn sich Verhalten oder Begriffe aendern,
- `git diff --check` sauber ist.

## Sprint 0: Projektfundament

Ziel: Repository, Produktgrenzen und Begriffe stabilisieren.

### Slice 0.1: Repository vorbereiten

Ziel:

Das Projekt ist als Git-Repository mit sinnvoller Grundstruktur nutzbar.

Umfang:

- Repository mit Branch `main`
- `README.md`
- `.gitignore`
- `.gitattributes`
- `.editorconfig`
- `.env.example`
- `pyproject.toml`
- Verzeichnisse fuer `docs`, `src`, `tests`, `scripts` und lokale `data`

Akzeptanzkriterien:

- Git-Status ist nach Initial Commit sauber.
- Lokale Laufzeitdaten werden ignoriert.
- Leere Arbeitsbereiche sind ueber `.gitkeep` versioniert.

### Slice 0.2: Dokumente ordnen

Ziel:

Vorhandene Konzeptdokumente sind auffindbar und nach Zweck sortiert.

Umfang:

- ADRs unter `docs/architecture`
- fachliche Konzepte unter `docs/concepts`
- Doku-Uebersicht unter `docs/README.md`

Akzeptanzkriterien:

- Alle vorhandenen Konzeptdateien sind erhalten.
- Die Doku-Uebersicht verlinkt alle zentralen Dokumente.

### Slice 0.3: MVP-Scope einfrieren

Ziel:

Der erste Produktumfang ist klar abgegrenzt.

Umfang:

- Local-first MVP
- manuelle Review
- LeadEngine, RatingEngine, DraftEngine
- lokale Konfiguration
- keine Versandautomatisierung
- keine oeffentliche Server-Komponente

Akzeptanzkriterien:

- Scope ist in README oder Konzeptdokumenten sichtbar.
- Ausgeschlossene Funktionen sind explizit benannt.

### Slice 0.4: Fachbegriffe konsolidieren

Ziel:

Die wichtigsten Begriffe werden einheitlich verwendet.

Umfang:

- `Profile`
- `SearchProfile`
- `TargetCandidate`
- `Target`
- `PipelineRun`
- `StatusLog`
- `RatingResult`
- `Draft`
- `ReviewQueue`

Akzeptanzkriterien:

- Begriffe sind in Domain-Modellen oder Dokumentation eindeutig.
- Begriffe widersprechen den bestehenden Konzeptdokumenten nicht.

## Sprint 1: Domain, Config und Storage

Ziel: Das Projekt bekommt ein tragfaehiges Datenfundament.

### Slice 1.1: Domain-Modelle

Ziel:

Zentrale Datenobjekte sind im Code modelliert.

Umfang:

- `Profile`
- `SearchProfile`
- `TargetCandidate`
- `Target`
- `PipelineRun`
- `PipelinePhase`
- `TargetStatus`
- `RatingResult`
- `Draft`
- `Evidence`

Akzeptanzkriterien:

- Modelle sind typsicher und importierbar.
- Pflichtfelder und optionale Felder sind nachvollziehbar.
- Tests pruefen Modell-Erzeugung und einfache Validierung.

### Slice 1.2: Konfigurationssystem

Ziel:

Infrastruktur- und Produkt-Konfiguration sind sauber getrennt.

Umfang:

- `.env` fuer lokale Infrastrukturwerte
- Code-Defaults fuer Produktwerte
- Prioritaet: `.env` beziehungsweise Environment vor Code-Default
- Defaults fuer Rating, LeadEngine-Budget, Fetching, Review Queue und Drafts

Akzeptanzkriterien:

- `.env.example` dokumentiert noetige Variablen.
- Tests pruefen Default-Werte und Environment-Overrides.
- Keine echten Secrets werden versioniert.

### Slice 1.3: SQLite-Schema

Ziel:

Lokale Persistenz ist vorbereitet.

Umfang:

- Tabellen fuer Targets
- Pipeline Runs
- Source Queries
- SERP Results
- Status Log
- Ratings
- Drafts
- Evidence oder Page Context

Akzeptanzkriterien:

- Schema kann lokal initialisiert werden.
- Tabellen enthalten Zeitstempel und nachvollziehbare IDs.
- Versionierte Daten wie Ratings und Drafts werden append-freundlich modelliert.

### Slice 1.4: Repository-Schicht

Ziel:

Code greift nicht direkt verstreut auf SQLite zu.

Umfang:

- Storage-API fuer Targets
- Storage-API fuer Pipeline Runs
- Storage-API fuer Status Logs
- Storage-API fuer Ratings und Drafts
- einfache Transaktionsgrenzen

Akzeptanzkriterien:

- CRUD-nahe Operationen sind getestet.
- Statuswechsel erzeugen nachvollziehbare History-Eintraege.
- Fehler bei fehlenden Datensaetzen sind kontrolliert.

### Slice 1.5: Datenfluss-Tests

Ziel:

Das Fundament ist gegen Regressionen abgesichert.

Umfang:

- Persistenztests mit temporaerer SQLite-Datenbank
- Tests fuer Config-Aufloesung
- Tests fuer Statuswechsel

Akzeptanzkriterien:

- Tests laufen ohne Netzwerk.
- Tests benoetigen keine echten API Keys.
- Lokale Testdaten bleiben ausserhalb von Git.

## Sprint 2: Pipeline-Skeleton

Ziel: Ein kompletter Pipeline-Lauf funktioniert technisch, noch ohne echte externe Provider.

### Slice 2.1: Pipeline-Orchestrator

Ziel:

Ein `PipelineRun` kann gestartet, verfolgt und beendet werden.

Umfang:

- Run-Erzeugung
- Phasensteuerung
- Status-Historie
- Fehlerstatus
- einfacher Resume-Ansatz

Akzeptanzkriterien:

- Ein Lauf schreibt Start, Phasenstatus und Abschluss.
- Fehlende oder fehlerhafte Phase bricht kontrolliert ab.
- Tests pruefen erfolgreichen und fehlerhaften Lauf.

### Slice 2.2: Fake LeadEngine

Ziel:

Die Pipeline kann ohne Netzwerk deterministische Kandidaten erzeugen.

Umfang:

- Fake Engine mit festen Kandidaten
- konfigurierbare Anzahl Ergebnisse
- Testdaten fuer unterschiedliche Domains und Dubletten

Akzeptanzkriterien:

- Pipeline-End-to-End-Test nutzt Fake LeadEngine.
- Ergebnisse sind reproduzierbar.

### Slice 2.3: Target Import und Dedupe

Ziel:

Kandidaten werden zu Targets importiert und Dubletten vermieden.

Umfang:

- Domain-Normalisierung
- URL-Normalisierung
- Importstatus
- Dedupe nach Domain oder Canonical URL

Akzeptanzkriterien:

- Doppelte Kandidaten erzeugen keine doppelten Targets.
- Importentscheidungen werden nachvollziehbar gespeichert.

### Slice 2.4: Minimale Review Queue

Ziel:

Targets koennen fuer manuelle Pruefung abgerufen werden.

Umfang:

- Query fuer Review-Kandidaten
- Sortierung nach Status und Prioritaet
- einfache Pagination

Akzeptanzkriterien:

- Review Queue liefert stabile Ergebnisse.
- Pagination ist getestet.

### Slice 2.5: End-to-End-Testlauf

Ziel:

Ein kompletter technischer Lauf ist automatisiert pruefbar.

Umfang:

- Suchprofil laden
- Fake-Kandidaten erzeugen
- Targets importieren
- Status schreiben
- Review Queue abrufen

Akzeptanzkriterien:

- Ein Test deckt den gesamten Skeleton-Lauf ab.
- Der Lauf benoetigt kein Netzwerk und keine Secrets.

## Sprint 3: LeadEngine MVP

Ziel: Aus einem Suchprofil echte Target-Kandidaten finden.

### Slice 3.1: Query Builder

Ziel:

Aus Suchprofil-Attributen entstehen viele kurze, kontrollierte Queries.

Umfang:

- Rollenbegriffe
- Regionen
- Tech-Keywords
- Branchenbegriffe
- Ausschlussbegriffe
- Template-Sets

Akzeptanzkriterien:

- Query-Fanout ist deterministisch.
- Query-Dedupe verhindert Wiederholungen.
- Tests pruefen typische Suchprofile.

### Slice 3.2: Query Budget

Ziel:

Discovery bleibt kontrollierbar und reproduzierbar.

Umfang:

- maximales Query-Budget
- Results pro Query
- Modus `explore`, `focused`, `refresh`
- Budget-Snapshots pro Lauf

Akzeptanzkriterien:

- Budget wird nie ueberschritten.
- Budgetwerte sind im Run nachvollziehbar.

### Slice 3.3: Provider-Abstraktion

Ziel:

Search Provider koennen ausgetauscht werden.

Umfang:

- Provider-Interface
- Fake Provider
- Brave-kompatibler Adapter
- Provider-Fehlerobjekte

Akzeptanzkriterien:

- LeadEngine haengt nicht direkt an einem konkreten Provider.
- Tests nutzen Fake Provider.
- Brave-Adapter ist isoliert testbar.

### Slice 3.4: SERP-Speicherung

Ziel:

Suchergebnisse bleiben nachvollziehbar.

Umfang:

- Source Queries
- SERP Results
- Query-Herkunft
- Provider-Metadaten
- Importstatus

Akzeptanzkriterien:

- Ergebnisse sind pro Lauf nachvollziehbar.
- Gleiche Query kann ueber Hash erkannt werden.

### Slice 3.5: Source Filter

Ziel:

Offensichtlich schlechte oder irrelevante Quellen werden frueh aussortiert.

Umfang:

- Denylist
- Jobboard-Filter
- Social- oder Aggregator-Filter
- Domain-Regeln
- Begruendung fuer Ausschluss

Akzeptanzkriterien:

- Ausschluss ist nachvollziehbar gespeichert.
- Filter sind konfigurierbar und getestet.

## Sprint 4: Fetcher, Extractor und Evidence

Ziel: Targets bekommen belastbaren Kontext.

### Slice 4.1: Fetcher

Ziel:

Target-Seiten koennen kontrolliert abgerufen werden.

Umfang:

- HTTP Fetching
- Timeout
- User-Agent
- Retry-Grenzen
- Fehlerklassifikation

Akzeptanzkriterien:

- Fetch-Ergebnisse enthalten Status und Metadaten.
- Netzwerkfehler erzeugen kontrollierte Fehlerstatus.

### Slice 4.2: Extractor

Ziel:

Aus HTML entstehen nutzbare Text- und Metadaten.

Umfang:

- Title
- Meta Description
- sichtbarer Haupttext
- relevante Abschnitte
- Links zu Karriere, Kontakt oder Impressum

Akzeptanzkriterien:

- HTML-Fixtures werden reproduzierbar extrahiert.
- Leere oder unbrauchbare Seiten werden erkannt.

### Slice 4.3: Evidence-Modell

Ziel:

Bewertungen und Drafts koennen auf Quellen verweisen.

Umfang:

- Evidence-Objekte
- Quelle
- Textauszug
- Kontexttyp
- Prioritaet

Akzeptanzkriterien:

- Evidence wird versioniert oder laufbezogen gespeichert.
- Ratings und Drafts koennen Evidence referenzieren.

### Slice 4.4: Fehlerverhalten

Ziel:

Fehlerhafte Targets bleiben im System bearbeitbar.

Umfang:

- Timeout
- HTTP-Fehler
- nicht lesbarer Inhalt
- fehlender Kontext
- Status-Log-Eintraege

Akzeptanzkriterien:

- Fehler fuehren nicht zum Verlust des Targets.
- Review Queue kann Fehlerfaelle anzeigen.

### Slice 4.5: Fixture-basierte Tests

Ziel:

Fetcher und Extractor sind ohne echte Webseiten testbar.

Umfang:

- HTML-Fixtures
- typische Firmenwebseite
- schlechte Quelle
- leere Seite
- Weiterleitung oder Fehlerseite

Akzeptanzkriterien:

- Tests laufen offline.
- Extraktionsergebnisse sind stabil.

## Sprint 5: RatingEngine MVP

Ziel: Targets werden nachvollziehbar bewertet.

### Slice 5.1: Rule Rating

Ziel:

Eine erste deterministische Bewertung funktioniert ohne LLM.

Umfang:

- Keyword-Matches
- Region
- Branche
- Ausschlusskriterien
- einfache Confidence

Akzeptanzkriterien:

- Rating ist reproduzierbar.
- Gruende werden strukturiert gespeichert.

### Slice 5.2: Score-Konfiguration

Ziel:

Schwellenwerte und Gewichtungen sind versioniert.

Umfang:

- Rating-Schwellen
- Gewichtungen
- Confidence-Regeln
- Config-Snapshot pro Lauf oder Rating

Akzeptanzkriterien:

- Aenderungen an Defaults sind nachvollziehbar.
- Tests pruefen Grenzwerte.

### Slice 5.3: AI Rating

Ziel:

Relevante Targets werden mit einem LLM-basierten Rating bewertet, ohne die deterministischen Gates zu umgehen.

Umfang:

- AI Rating nur nach bestandenem Rule-Gate
- Page Context Builder mit Budget und Priorisierung
- klares JSON-Schema fuer AI-Ausgabe
- `ai_score`, `raw_confidence`, Gruende, Risiken und Quellen
- Fehlerbehandlung fuer Provider-Fehler, ungueltige Antworten und fehlende Quellen

Akzeptanzkriterien:

- Tests nutzen einen Fake-AI-Provider und benoetigen kein Netzwerk.
- AI Rating startet nicht bei hartem Stopper oder unzureichendem Kontext.
- Ungueltige AI-Antworten fuehren zu `rating_partial` und `recommended_action = review`.

### Slice 5.4: Evidence Check

Ziel:

Rating-Gruende bleiben belegbar.

Umfang:

- Zuordnung von Gruenden zu Evidence
- Erkennung unbelegter Aussagen
- Status fuer unzureichenden Kontext

Akzeptanzkriterien:

- Rating darf keine nicht belegten Gruende als sicher ausgeben.
- Fehlende Evidence fuehrt zu `rating_partial` und `recommended_action = review`.

### Slice 5.5: Decision Merge

Ziel:

Aus Teilbewertungen entsteht eine klare Entscheidung.

Umfang:

- `skip`
- `review`
- `draft`

Akzeptanzkriterien:

- Entscheidung ist aus Scores und Regeln ableitbar.
- Niedrige Confidence wird sichtbar.
- Harte Stopper erzwingen `skip`, auch wenn Teil-Scores positiv sind.

### Slice 5.6: Rating-Versionen

Ziel:

Neue Ratings ersetzen alte nicht blind.

Umfang:

- Rating-Version
- Rating-Zeitpunkt
- Config-Snapshot
- aktives Rating pro Target

Akzeptanzkriterien:

- Re-Rating erzeugt neue Version.
- Alte Versionen bleiben lesbar.

## Sprint 6: DraftEngine MVP

Ziel: Fuer geeignete Targets entstehen pruefbare Entwuerfe.

### Slice 6.1: Draft Context Builder

Ziel:

Drafts erhalten kompakten, belegbaren Kontext.

Umfang:

- Profil
- Target
- Rating
- Evidence
- Sprache und Draft-Typ

Akzeptanzkriterien:

- Kontext bleibt innerhalb definierter Budgets.
- Fehlender Kontext wird kontrolliert gemeldet.

### Slice 6.2: Template-basierte Drafts

Ziel:

Der Draft-Fluss funktioniert ohne LLM.

Umfang:

- einfache Templates
- Sprache
- Draft-Typen
- Platzhaltervalidierung

Akzeptanzkriterien:

- Drafts sind reproduzierbar.
- Tests pruefen Pflichtfelder und Ausgabe.

### Slice 6.3: Draft-Validierung

Ziel:

Drafts werden vor Review geprueft.

Umfang:

- Mindest- und Maximal-Laenge
- verbotene Aussagen
- fehlende Belege
- Sprache
- Pflichtbestandteile

Akzeptanzkriterien:

- Ungueltige Drafts erhalten Fehlerstatus.
- Validierungsgruende sind sichtbar.

### Slice 6.4: Draft-Versionen

Ziel:

Regeneration und Nutzerbearbeitung bleiben nachvollziehbar.

Umfang:

- Draft-Version
- Ursprung `generated` oder `user_edited`
- aktiver Draft
- Historie

Akzeptanzkriterien:

- Neue Drafts ueberschreiben alte Versionen nicht.
- Bearbeitete Drafts bleiben erkennbar.

### Slice 6.5: Review-Status

Ziel:

Drafts fuehren nie zu automatischer Kontaktaufnahme.

Umfang:

- Status `needs_review`
- Status `approved`
- Status `rejected`
- manuelle Entscheidung

Akzeptanzkriterien:

- Kein Codepfad markiert Drafts automatisch als versendet.
- UI/API koennen Review-Status lesen.

## Sprint 7: Lokale API oder CLI

Ziel: Das System wird lokal bedienbar.

### Slice 7.1: CLI fuer Pipeline Runs

Ziel:

Ein Nutzer kann lokal einen Lauf starten.

Umfang:

- Suchprofil aus Datei laden
- Pipeline starten
- Run-ID ausgeben
- Status anzeigen

Akzeptanzkriterien:

- CLI funktioniert ohne UI.
- Fehler werden lesbar ausgegeben.

### Slice 7.2: API-Skeleton

Ziel:

Die wichtigsten Produktobjekte sind ueber API erreichbar.

Umfang:

- Runs
- Targets
- Ratings
- Drafts
- Review Queue

Akzeptanzkriterien:

- API leakt interne Engine-Grenzen nicht unnoetig.
- Endpunkte sind klein und testbar.

### Slice 7.3: Reprocessing-Aktionen

Ziel:

Einzelne Targets koennen gezielt neu verarbeitet werden.

Umfang:

- neu fetchen
- neu bewerten
- Draft neu erzeugen
- Run- oder Target-bezogene Historie

Akzeptanzkriterien:

- Reprocessing startet kleinsten sinnvollen Neudurchlauf.
- Nutzer sieht, welche Phase erneut ausgefuehrt wird.

### Slice 7.4: Export

Ziel:

Review-Ergebnisse koennen lokal weiterverwendet werden.

Umfang:

- JSON Export
- CSV Export
- optional Markdown Export
- keine Secrets im Export

Akzeptanzkriterien:

- Export ist reproduzierbar.
- Exportierte Felder sind dokumentiert.

## Sprint 8: UI MVP

Ziel: Manuelle Review wird komfortabel.

### Slice 8.1: Review Queue Ansicht

Ziel:

Nutzer sehen die wichtigsten Targets priorisiert.

Umfang:

- Target-Liste
- Score
- Status
- Risiko oder Confidence
- Pagination
- Sortierung

Akzeptanzkriterien:

- Nutzer kann Targets effizient scannen.
- Status und Score sind eindeutig sichtbar.

### Slice 8.2: Target Detail

Ziel:

Ein Target kann nachvollziehbar geprueft werden.

Umfang:

- Stammdaten
- Quellen
- Evidence
- Rating-Gruende
- Drafts
- Status-Historie

Akzeptanzkriterien:

- Jede Bewertung ist auf Quellen zurueckfuehrbar.
- Draft und Evidence sind gemeinsam sichtbar.

### Slice 8.3: Manuelle Aktionen

Ziel:

Review-Entscheidungen koennen direkt getroffen werden.

Umfang:

- approve
- reject
- blacklist oder denylist
- reprocess
- Draft bearbeiten

Akzeptanzkriterien:

- Aktionen schreiben Status-Historie.
- Kritische Aktionen sind bewusst und nachvollziehbar.

### Slice 8.4: Run Monitor

Ziel:

Pipeline-Laeufe sind beobachtbar.

Umfang:

- Laufstatus
- Phasen
- Fehler
- Fortschritt
- betroffene Targets

Akzeptanzkriterien:

- Nutzer erkennt, ob ein Lauf aktiv, fertig oder fehlgeschlagen ist.
- Fehler enthalten naechste sinnvolle Aktion.

## Sprint 9: Qualitaet, Sicherheit und Betrieb

Ziel: Der MVP wird robust genug fuer echte lokale Nutzung.

### Slice 9.1: Logging und Fehleranalyse

Ziel:

Fehler sind lokal nachvollziehbar, ohne sensible Daten unnoetig offenzulegen.

Umfang:

- strukturierte Logs
- Log-Level
- keine API Keys in Logs
- Fehlerklassen

Akzeptanzkriterien:

- Logs helfen bei lokaler Diagnose.
- Secrets werden nicht geloggt.

### Slice 9.2: Testausbau

Ziel:

Zentrale Workflows sind gegen Regressionen abgesichert.

Umfang:

- Unit-Tests
- Storage-Tests
- Pipeline-Tests
- Fixture-basierte Integrationstests

Akzeptanzkriterien:

- Tests laufen ohne Netzwerk.
- Tests decken Erfolgs- und Fehlerpfade ab.

### Slice 9.3: Datenschutz-Check

Ziel:

Local-first Annahmen werden praktisch eingehalten.

Umfang:

- `.gitignore` pruefen
- lokale Daten pruefen
- Export-Felder pruefen
- Logs pruefen

Akzeptanzkriterien:

- Keine echten Profile oder Secrets sind versioniert.
- Export und Logs enthalten keine unnoetigen sensiblen Daten.

### Slice 9.4: Setup-Dokumentation

Ziel:

Das Projekt ist lokal reproduzierbar aufsetzbar.

Umfang:

- Installation
- lokale Konfiguration
- erster Pipeline-Lauf
- Tests
- typische Fehler

Akzeptanzkriterien:

- Neue lokale Umgebung kann aus der Doku gestartet werden.
- Bekannte Fehler haben klare Hinweise.

## Sprint 10: Echte lokale Pipeline stabilisieren

Ziel: Die lokale End-to-End-Pipeline wird fuer echte Review-Arbeit wiederholbar
und gezielt nachbearbeitbar.

### Slice 10.1: Reprocessing ausfuehren

Ziel:

UI-Aktionen loesen echte Engine-Schritte aus, statt nur Status zu setzen.

Umfang:

- `refetch` fuehrt Fetch, Extract, Rating und Draft-Handoff erneut aus.
- `rerate` bewertet bestehende Evidence erneut.
- `regenerate-draft` erzeugt einen neuen Draft aus dem letzten Rating.
- Einzelaktionen schreiben keinen kuenstlichen Pipeline Run.

Akzeptanzkriterien:

- Reprocessing-Statuslogs duerfen `pipeline_run_id = NULL` haben.
- Statuslogs enthalten Trigger, Action und Endpoint in den Metadaten.
- Die Review Queue bleibt nach Reprocessing konsistent.

### Slice 10.2: Mehrseitiger Fetch

Ziel:

Targets werden nicht nur ueber die Basis-URL bewertet, sondern ueber relevante
gleiche-Domain-Seiten.

Umfang:

- Karriere-, Job-, Kontakt-, Impressum- und About-Links erkennen.
- Maximalzahl pro Target begrenzen.
- Fehlgeschlagene Seiten isoliert behandeln.

Akzeptanzkriterien:

- Mindestens eine brauchbare Seite fuehrt nicht zu `fetch_failed`.
- Teilfehler werden als `fetch_partial` protokolliert.
- Evidence wird pro brauchbarer Seite gespeichert.

### Slice 10.3: LLM-Robustheit

Ziel:

AI-Ausfaelle blockieren den lokalen Workflow nicht.

Umfang:

- Provider-Fehler und ungueltige Antworten abfangen.
- Rule Score und Evidence behalten.
- Target als `rating_partial` in die Review geben.

Akzeptanzkriterien:

- AI-Fehler erzeugen `recommended_action = review`.
- Fehlerklasse und Fehlermeldung werden am Rating gespeichert.
- Es wird kein automatischer Draft aus fehlerhaftem AI Rating erzeugt.

### Slice 10.4: Review-UI verdichten

Ziel:

Die lokale UI zeigt die entscheidenden Review-Signale kompakter an.

Umfang:

- Rating-Fehler sichtbar machen.
- Rating-Gruende und Risiken anzeigen.
- Reprocessing-Antworten nach UI-Aktionen verarbeiten.

Akzeptanzkriterien:

- Nutzer sieht Gruende, Risiken und Fehler ohne Datenbankzugriff.
- Manuelle Aktionen und Reprocessing bleiben lokal bedienbar.

### Slice 10.5: Echter Pilotlauf

Ziel:

Die konfigurierte Pipeline kann kontrolliert mit kleinem Budget gegen echte
Provider laufen.

Umfang:

- CLI-Budgets direkt an die LeadEngine durchreichen.
- Fetch-Konfiguration aus `.env` nutzen.
- Ergebniszaehler fuer Fetch, Evidence, Rating, Draft und Fehler ausgeben.

Akzeptanzkriterien:

- `run-configured --request-budget 1 --results-per-query 1` bleibt begrenzt.
- Externe Fehler beenden nicht den gesamten Lauf.
- Der Lauf endet bei Teilfehlern als `completed_with_errors`.

## Sprint 11: LeadEngine Ergebnisqualitaet

Ziel: Die LeadEngine liefert weniger Jobportale und mehr direkte, pruefbare
Ziel-Domains. Der Fokus liegt auf besserer Discovery, nicht auf finalem Scoring.

### Slice 11.1: Source-Klassifikation und Jobportal-Denylist

Ziel:

SERP-Treffer werden frueh nach Quellentyp klassifiziert, damit Aggregatoren,
Jobboersen und Social-Profile nicht wie echte Zielunternehmen behandelt werden.

Umfang:

- systemische Denylist fuer Jobportale und Aggregatoren
- Quellentypen wie `company`, `job_board`, `agency_directory`, `social`,
  `unknown`
- `blocked_source` fuer systemisch blockierte Quellen
- Konfiguration fuer lokale Erweiterung der Denylist

Akzeptanzkriterien:

- Bekannte Jobportale wie StudentJob, StepStone, Indeed und LinkedIn Jobs werden
  nicht als normale Targets importiert.
- Blockierte Treffer bleiben in SERP-Logs nachvollziehbar.
- Nutzer-Blacklist (`blacklisted`) bleibt getrennt von Source-Denylist
  (`blocked_source`).

### Slice 11.2: Query-Templates fuer direkte Ziel-Domains

Ziel:

Die Query Builder erzeugen Suchanfragen, die eher Unternehmensseiten als
Aggregatoren finden.

Umfang:

- Templates fuer Firmen-Karriereseiten
- Templates fuer lokale IT-Dienstleister, Agenturen und Mittelstand
- negative Query-Terme fuer grosse Jobboersen
- Template-Sets pro Suchmodus, z. B. `company_direct`, `local_services`,
  `career_pages`

Akzeptanzkriterien:

- Queries bleiben kurz genug fuer Brave.
- Mindestens ein Template-Set bevorzugt direkte Firmen-Websites.
- Query-Text, Template und Score werden weiter in `source_queries` gespeichert.

### Slice 11.3: Domain-Qualitaet und SERP-Priorisierung

Ziel:

SERP-Ergebnisse werden vor dem Import nach wahrscheinlicher Target-Qualitaet
sortiert.

Umfang:

- Domain-Qualitaetsmerkmale speichern
- direkte Unternehmensdomain hoeher priorisieren
- Portal-/Aggregator-Signale abwerten
- Karriere-/Kontakt-/About-URL-Signale aufwerten
- SERP-Rang nicht blind uebernehmen

Akzeptanzkriterien:

- Bei gleicher Query wird eine direkte Unternehmensdomain vor Jobboersen
  importiert.
- Ranking-Metadaten sind im SERP-Result nachvollziehbar.
- LeadEngine bleibt eine Vorfilterung; finale Passung bleibt RatingEngine.

### Slice 11.4: Domain-Dedupe und Fundstellen-Buendelung

Ziel:

Mehrere Treffer zur gleichen Domain werden als ein Kandidat behandelt, ohne
nuetzliche Fundstellen zu verlieren.

Umfang:

- Canonical Domain normalisieren
- `www`, Tracking-Parameter und offensichtliche Duplikate bereinigen
- beste Fundstellen je Domain sammeln
- Kandidaten-Metadaten um `discovery_urls` und `best_source_url` erweitern

Akzeptanzkriterien:

- Eine Domain erzeugt pro Lauf nur einen Target-Kandidaten.
- Alternative Fundstellen bleiben fuer Fetch/Evidence nutzbar.
- `duplicate_domain` bleibt ein LeadEngine-Status, kein Importstatus.

### Slice 11.5: Feedback aus Review-Aktionen

Ziel:

Manuelle Entscheidungen verbessern spaetere LeadEngine-Laeufe.

Umfang:

- abgelehnte Jobportale fuer Denylist-Vorschlaege markieren
- `approved`, `rejected`, `blacklisted` als Discovery-Signal auswerten
- Suchprofil-Anpassungen fuer schlechte Treffer dokumentieren
- keine automatische Blacklist ohne Nutzerentscheidung

Akzeptanzkriterien:

- Wiederholte schlechte Domains koennen sichtbar vorgeschlagen werden.
- Nutzerentscheidung bleibt explizit.
- LeadEngine nutzt Feedback nur als lokales Signal.

### Slice 11.6: LeadEngine-Metriken und Pilot-Auswertung

Ziel:

Discovery-Qualitaet wird messbar, bevor weitere Provider oder groessere Budgets
genutzt werden.

Umfang:

- Kennzahlen pro Lauf:
  - Query Count
  - SERP Result Count
  - Blocked Source Count
  - Direct Domain Count
  - Duplicate Domain Count
  - Imported Target Count
- kleiner Pilotlauf mit festen Suchprofilen
- Vergleich vor/nach Source-Filtern und Template-Sets

Akzeptanzkriterien:

- Ein Lauf zeigt, wie viele Treffer wegen Portalen blockiert wurden.
- Ergebnisqualitaet laesst sich ohne manuelle DB-Abfrage einschaetzen.
- Tests decken Query Builder, Source-Filter und Dedupe ab.

## Sprint 12: Produktisierung der lokalen UI

Ziel: Die lokale UI wird vom Demonstrator zur nutzbaren Arbeitsoberflaeche fuer
begrenzte echte Runs. Der Fokus liegt auf Bedienbarkeit, Transparenz und kleinen
kontrollierten Budgets, nicht auf neuen Use-Case-Typen.

### Slice 12.1: Konfigurierbare UI-Runs

Ziel:

Nutzer koennen echte, begrenzte Pipeline-Laeufe aus der UI starten.

Umfang:

- Search Profile auswaehlen
- Use Case auswaehlen
- Provider-Modus `fake`, `brave` oder `configured` waehlen
- Request- und Result-Budget setzen
- Start-Button gegen den bestehenden `run-configured`-Pfad anbinden
- laufende und abgeschlossene Runs in der UI aktualisieren

Akzeptanzkriterien:

- Fake Runs bleiben fuer Entwicklung und Tests verfuegbar.
- Ein echter Run kann mit kleinem Budget aus der UI gestartet werden.
- Provider-Fehler beenden nicht die gesamte UI-Sitzung.
- Der Run zeigt Status, Zaehler und Fehler ohne Datenbankzugriff.

### Slice 12.2: Provider-Status und Light-LLM-Routing

Ziel:

Die UI zeigt, ob lokale Provider und Light-LLM-Konfiguration nutzbar sind.

Umfang:

- Brave-Konfiguration ohne Secret-Anzeige pruefen
- Ollama-/Qwen-Erreichbarkeit pruefen
- OpenAI-Konfiguration nur als vorhanden/nicht vorhanden anzeigen
- LLM-Modus `off` und `light` sichtbar machen
- Heavy-Modelle als spaetere optionale Erweiterung markieren

Akzeptanzkriterien:

- Secrets werden nie in der UI oder in Exporten angezeigt.
- Nutzer sieht fehlende Provider-Konfiguration vor dem Run.
- Light-Routing ist fuer lokale Tests auswaehlbar.
- Heavy Thinking ist nicht noetig, um den MVP weiterzuentwickeln.

### Slice 12.3: Evidence- und Rating-Erklaerung

Ziel:

Review-Entscheidungen werden nachvollziehbar, ohne Logs oder Datenbanktabellen
zu lesen.

Umfang:

- Evidence-Snippets, Quellen-URL und Quellentyp gemeinsam anzeigen
- Source-Quality-Signale und Risiken anzeigen
- Rating-Kriterien mit Score-Beitrag darstellen
- Draft-Fehler und LLM-Fehler sichtbar machen

Akzeptanzkriterien:

- Eine Review-Zeile erklaert, warum `skip`, `review` oder `draft` empfohlen
  wurde.
- Nutzer kann schlechte Quellen direkt erkennen.
- Fehlende Evidence wird als eigener Zustand angezeigt.

### Slice 12.4: Review-Feedback fuer spaetere Discovery

Ziel:

Manuelle Review-Aktionen verbessern spaetere LeadEngine-Laeufe lokal.

Umfang:

- `reject` und `blacklist` als Feedback-Signale speichern
- wiederholt schlechte Domains fuer Denylist-Vorschlaege markieren
- Nutzerentscheidung von systemischer Source-Denylist getrennt halten
- Feedback in SourceQualityClassifier oder LeadEngine-Priorisierung auswerten

Akzeptanzkriterien:

- Eine blacklisted Domain wird in spaeteren Runs nicht erneut importiert.
- Wiederholte Rejects werden als Vorschlag sichtbar, aber nicht automatisch
  blockiert.
- `blocked_source` und Nutzer-Blacklist bleiben begrifflich getrennt.

### Slice 12.5: Strukturierter Use-Case-Editor

Ziel:

Eigene Use Cases lassen sich ohne direkte JSON-Bearbeitung pflegen.

Umfang:

- strukturierte Formulare fuer Attribute, Queries, Quellen, Rating und Drafts
- Query Preview auf Basis der aktuellen Attribute
- Validierung mit klaren Fehlern
- Gewichte muessen exakt zu `100` summieren
- JSON-Ansicht nur als Expertenmodus behalten

Akzeptanzkriterien:

- Ein einfacher Use Case kann ohne JSON geschrieben werden.
- Template-Variablen und Attribute sind in der UI eindeutig verbunden.
- Ungueltige Policies koennen nicht gespeichert werden.

### Slice 12.6: Import und Export als Dateiworkflow

Ziel:

Use Cases koennen sauber geteilt, gesichert und wieder importiert werden.

Umfang:

- Export als Datei-Download
- Import per Datei-Auswahl
- Konfliktbehandlung bei gleicher ID
- Privacy-Check vor Export
- Validierungsbericht vor Import

Akzeptanzkriterien:

- Export enthaelt keine Secrets.
- Import zeigt Fehler vor dem Speichern.
- Bestehende Use Cases werden nicht versehentlich ueberschrieben.

### Slice 12.7: Metriken und Pilot-Auswertung

Ziel:

Echte kleine Runs liefern auswertbare Signale fuer Engine-Verbesserungen.

Umfang:

- Run-Metriken in CLI und UI anzeigen
- Source-Type-Verteilung anzeigen
- blockierte, importierte, doppelte und geratete Targets zaehlen
- Request-/Provider-Zaehler erfassen
- Pilotlaeufe mit festen Profilen dokumentieren

Akzeptanzkriterien:

- Nach einem Run ist sichtbar, wo Treffer verloren oder blockiert wurden.
- Ergebnisqualitaet kann ohne manuelle Datenbankanalyse bewertet werden.
- LeadEngine-Verbesserungen koennen gegen vorherige Runs verglichen werden.

### Slice 12.8: UI-Regressionstests

Ziel:

Die lokale UI bleibt bei weiteren Engine-Aenderungen stabil.

Umfang:

- Playwright-Smoke-Test fuer Review, Use Cases, Profile und Runs
- Test fuer Fake Run aus der UI
- Test fuer Use-Case-Clone und Validierungsfehler
- Screenshot-Pruefung fuer Desktop-Breite

Akzeptanzkriterien:

- UI-Basispfade laufen automatisiert.
- Navigation zwischen Unterseiten bricht nicht.
- Tests koennen lokal ohne echte Provider-Secrets laufen.

## Sprint 13: UI-Einstellungen und Nutzerkontrolle

Ziel: Nutzer koennen die lokale Pipeline ohne Code sinnvoll konfigurieren. Sprint
12 macht echte Runs aus der UI moeglich; Sprint 13 schliesst die Luecken bei
Search Profiles, Use-Case-spezifischen Eingaben, Provider-/LLM-Auswahl und
lokaler Policy-Verwaltung.

### Slice 13.1: Search Profiles erstellen und bearbeiten

Ziel:

Search Profiles sind vollstaendig ueber die UI verwaltbar.

Umfang:

- neues Search Profile anlegen
- bestehendes Search Profile bearbeiten
- Rollen, Regionen, Tech-, Branchen- und Ausschlussbegriffe pflegen
- freie Attribute speichern
- Use Case zuweisen
- Search Profile loeschen oder archivieren

Akzeptanzkriterien:

- Ein Nutzer kann einen neuen Run starten, ohne vorher CLI oder Datenbank zu
  nutzen.
- Search Profiles behalten ihre Use-Case-Zuordnung.
- Ungueltige leere Pflichtwerte werden vor dem Speichern angezeigt.

### Slice 13.2: Dynamische Run-Maske aus Use Case

Ziel:

Die Run-Eingaben passen sich an den gewaehlten Use Case an.

Umfang:

- Felder aus `attribute_schema` rendern
- Feldtypen `text`, `list`, `number`, `boolean` und `select` bedienen
- Pflichtfelder markieren und validieren
- Quick-Run-Werte in SearchProfile-Attribute uebernehmen
- generische Labels wie `Rollen / Topics` durch Use-Case-Labels ersetzen

Akzeptanzkriterien:

- `company_osint` zeigt `topics`, `industries` und `regions`.
- `application_student` zeigt Rollen, Technologien, Branchen und Regionen.
- Der Run-Payload enthaelt nur valide Attribute fuer den gewaehlten Use Case.

### Slice 13.3: Run-Ausfuehrung granular steuern

Ziel:

Nutzer koennen kontrollieren, welche Pipeline-Teile pro Run ausgefuehrt werden.

Umfang:

- Provider-Modus `fake`, `brave`, `configured`
- LLM-Modus `off`, `light`
- Fetch-Modus `fake` oder `http`
- Phasen-Auswahl:
  - nur Discovery
  - Discovery und Fetch
  - Full Pipeline
  - nur Rerating
- Draft-Erzeugung an/aus
- Request Budget, Results per Query und Max Pages per Target einstellen

Akzeptanzkriterien:

- Kleine echte Runs bleiben strikt budgetiert.
- Discovery-only Runs erzeugen keine Fetch-/Rating-Arbeit.
- Drafts koennen pro Run deaktiviert werden.
- UI zeigt die aktiven Phasen im Run-Datensatz.

### Slice 13.4: Provider- und Modell-Auswahl

Ziel:

Die lokale UI macht Provider-Konfiguration sichtbar und auswaehlbar, ohne Secrets
offenzulegen.

Umfang:

- Brave-Status anzeigen
- Ollama-Erreichbarkeit anzeigen
- installierte Ollama-Modelle auflisten
- Light-Modell pro Run waehlen
- Default-Light-Modell lokal speichern
- Heavy-Modell weiter als optional markieren

Akzeptanzkriterien:

- Secrets erscheinen nie in UI, Logs oder Exporten.
- Nutzer sieht, ob das gewaehlte Modell lokal verfuegbar ist.
- `qwen3:8b`, `qwen3.5:27b` und `qwen3:30b-a3b-q4_K_M` koennen ausgewaehlt
  werden, wenn Ollama sie meldet.

### Slice 13.5: Lokale Domain-Policies verwalten

Ziel:

Nutzer koennen Quellenentscheidungen direkt in der UI nachvollziehen und
anpassen.

Umfang:

- Blacklist anzeigen
- Domain manuell zur Blacklist hinzufuegen
- Domain aus Blacklist entfernen
- Denylist-Vorschlaege aus wiederholten Rejects anzeigen
- Preferred Domains pflegen
- Blocked Domains pro Use Case oder lokalem Profil pflegen
- Trennung zwischen Nutzer-Blacklist und systemischer Source-Denylist anzeigen

Akzeptanzkriterien:

- Eine blacklisted Domain wird in spaeteren Runs nicht erneut importiert.
- Wiederholte Rejects erzeugen nur Vorschlaege, keine automatische Sperre.
- Nutzer kann eine versehentlich blacklisted Domain wieder freigeben.

### Slice 13.6: Query- und Source-Preview vor dem Run

Ziel:

Nutzer sehen vor dem Start, welche Suchanfragen und Quellenregeln aktiv sind.

Umfang:

- gerenderte Query Templates anzeigen
- Template-Variablen mit konkreten Attributwerten darstellen
- Source Policy Preview anzeigen
- bevorzugte und blockierte Quellentypen anzeigen
- erwartete Budgets je Query anzeigen

Akzeptanzkriterien:

- Ein Run kann vor dem Start fachlich plausibilisiert werden.
- Fehlende Template-Variablen blockieren den Run.
- Preferred, context und blocked source types sind sichtbar.

### Slice 13.7: Strukturierter Use-Case-Editor Ausbau

Ziel:

Use Cases lassen sich dauerhaft ohne JSON-Kenntnisse pflegen.

Umfang:

- Attribute als Formularzeilen bearbeiten
- Query Templates als einzelne Eintraege bearbeiten
- Source Types per Mehrfachauswahl pflegen
- Rating-Kriterien mit Gewichtung per Formular bearbeiten
- Draft Policy strukturiert bearbeiten
- JSON-Modus nur als Expertenansicht

Akzeptanzkriterien:

- Ein einfacher neuer Use Case kann ohne JSON erstellt werden.
- Gewichtssumme `100` wird direkt beim Bearbeiten validiert.
- Ungueltige Source Types, Review Actions und Draft Sections werden klar
  angezeigt.

### Slice 13.8: Lokale Defaults und Diagnose

Ziel:

Wiederkehrende lokale Einstellungen muessen nicht pro Run neu gesetzt werden.

Umfang:

- Default Provider speichern
- Default LLM-Modus speichern
- Default Light-Modell speichern
- Default Budgets speichern
- Fetch-Timeout und Max Pages per Target anzeigen
- Diagnose-Seite fuer Provider-, Datenbank- und Modellstatus

Akzeptanzkriterien:

- Defaults werden lokal persistiert.
- Diagnose zeigt Konfigurationsprobleme ohne Secrets.
- Nutzer kann erkennen, ob ein Run wegen Provider, Modell, Budget oder Policy
  scheitern wuerde.

## Sprint 14: Engine-Qualitaet und Evaluationsbasis

Ziel: Nach dem ersten echten lokalen OSINT-Lauf werden LeadEngine, Evidence,
Rating und Draft nicht blind optimiert, sondern gegen kleine, feste
Evaluationsfaelle verbessert.

### Slice E1: Source-Quality-Evaluation-Baseline

Status: umgesetzt.

Ziel:

Die SourceQualityClassifier-Qualitaet wird messbar, bevor Heuristiken geaendert
werden.

Umfang:

- echte Treffer aus lokalem Run `#19` als Fixture erfassen
- Kontrollfaelle fuer `company_site`, `directory`, `news`, `official_site` und
  `job_board` erfassen
- erwartete Source-Type- und Import-Action-Entscheidungen festhalten
- stabile Faelle als normale Regressionstests ausfuehren
- bekannte Fehlklassifizierung `regiomanager.de` als naechsten E2-Fix
  dokumentieren

Akzeptanzkriterien:

- `tests/fixtures/source_quality_e1_baseline.json` enthaelt die
  Evaluationsfaelle.
- `test_source_quality_e1_baseline_stable_cases` prueft die stabilen Faelle.
- Die Baseline laeuft ohne echte Provider-Secrets.

### Slice E2: Source Classification verbessern

Status: umgesetzt.

Ziel:

Die bekannte Fehlklassifizierung aus E1 wird behoben und weitere
publisher-/directory-aehnliche Domains werden als Kontextquellen behandelt.

Umfang:

- `regiomanager.de` als `directory` oder `news` klassifizieren
- Ranking-/Toplisten-Pfade als Directory-/Listing-Signal nutzen
- Import-Policy fuer Kontextquellen gegen direkte Targets schaerfen
- E1-`expectedFailure` in einen normalen Regressionstest ueberfuehren

Akzeptanzkriterien:

- `regiomanager.de` wird nicht mehr als `company_site/import` behandelt.
- Kontextquellen bleiben als SERP-Kontext nachvollziehbar, werden aber nicht als
  Zielunternehmen importiert.
- E1-Baseline bleibt gruen.

### Slice E3: Kontextquellen fuer Evidence nutzbar machen

Status: umgesetzt als Context-Source-Sichtbarkeit und API-Basis.

Ziel:

`review_source`-Treffer sollen nicht als Targets importiert werden, aber fuer
spaetere Evidence und Kontextrecherche verwertbar bleiben.

Umfang:

- `review_source`-SERP-Ergebnisse mit Query- und Source-Quality-Metadaten
  abrufbar machen
- Kontextquellen ueber Search Profile, Use Case und Pipeline Run einordnen
- Review-UI sichtbar machen, welche Kontextquellen zu einem Run gehoeren
- Context-Source-Zaehler in Run-Stats aufnehmen
- keine Vermischung mit Target-Status und Target-Evidence

Akzeptanzkriterien:

- Kontextquellen werden nicht als Zielunternehmen geratet.
- `GET /api/context-sources` liefert `review_source`-Treffer mit Query,
  Source-Quality-Signalen und Run-Kontext.
- Runs zeigen Kontextquellen in der lokalen UI.
- Review Queue bleibt auf primaere Targets fokussiert.

Noch offen fuer den naechsten Evidence-Ausbau:

- Kontextquellen gezielt fetchbar machen.
- Kontextquellen einem konkreten Target zuordnen.
- Aus Kontextquellen typisierte Evidence ableiten.

### Slice E4: Query Quality pro Use Case verbessern

Status: umgesetzt.

Ziel:

Use-Case-Queries erzeugen weniger breite SERP-Treffer und vermeiden bekannte
irrelevante Query-Richtungen.

Umfang:

- `query_policy.exclude_terms` einfuehren
- Profil-`exclude_keywords` und Use-Case-`exclude_terms` als negative Suchterme
  an generierte Queries anhaengen
- manuelle Queries unveraendert lassen
- `company_osint` von breiten Anbieter-Queries auf direkte Unternehmens-,
  Kontakt-, Impressum- und Services-Queries umstellen
- `application_student` ohne OSINT-Default-Ausschluesse lassen
- Use-Case-Editor um Exclude Terms erweitern

Akzeptanzkriterien:

- OSINT-Queries enthalten negative Terme wie `-jobs` und `-stellenangebote`.
- Profil-Ausschluesse wie `ranking portal` werden als `-"ranking portal"`
  gerendert.
- Manuelle Queries bleiben exakt.
- Application-Queries behalten Bewerbungs-/Karriere-Intent.
- Tests decken Template-Reihenfolge, Ausschluesse und Use-Case-Trennung ab.

### Slice E5: Evidence Engine mit typisierten Belegen

Status: umgesetzt.

Ziel:

Evidence wird nicht mehr nur als Seitentext gespeichert, sondern bekommt eine
stabile Typisierung und Herkunft. Kontextquellen koennen einem Target
nachvollziehbar als Evidence zugeordnet werden.

Umfang:

- `EvidenceEngine` fuer Target-Page- und Context-Source-Evidence einfuehren
- Page-Evidence mit `evidence_type`, `provenance`, `page_id`, `page_type` und
  `source_url` taggen
- Context-Source-Evidence aus `review_source`-SERP-Ergebnissen erzeugen
- Context-Source-Zuordnung ueber `serp_results.target_id` speichern
- API `POST /api/targets/{id}/attach-context-source` bereitstellen
- Evidence-UI um Evidence Type, Context Type, Source Type und Query-Bezug
  erweitern
- Rating-Payload um Evidence Type, Provenance, Source Type und
  `context_source_id` erweitern

Akzeptanzkriterien:

- Target-Page-Evidence enthaelt z. B. `target_career` oder `target_contact`.
- Context-Source-Evidence enthaelt z. B. `context_directory`,
  `provenance = context_source` und die urspruengliche `context_source_id`.
- Context Sources bleiben keine primaeren Targets, koennen aber manuell einem
  Target als Evidence zugeordnet werden.
- Zuordnung ist idempotent und erzeugt fuer dieselbe Context Source keine
  doppelte Evidence.
- Rating bekommt die typisierten Evidence-Metadaten im `evidence_json`.
- Tests decken EvidenceEngine, Storage-Zuordnung, API und Pipeline-Integration
  ab.

## Empfohlene Reihenfolge

Die Sprints 0 bis 10 bilden den lokalen MVP-Pfad. Sprint 11 verbessert die
LeadEngine-Qualitaet. Sprint 12 produktisiert die UI, damit echte kleine Runs
kontrolliert bedienbar werden. Sprint 13 macht die UI fuer eigene lokale
Arbeitsweisen konfigurierbar. Sprint 14 startet die messbare Engine-Optimierung.
Danach ist die sinnvolle Reihenfolge:

1. E6 RatingEngine-Kriterien an Evidence-Typen koppeln.
2. DraftEngine erst danach weiter optimieren.
