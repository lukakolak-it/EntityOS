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

## Empfohlene Reihenfolge

Die Sprints 0 bis 10 bilden den lokalen MVP-Pfad. Sprint 11 verbessert die
LeadEngine-Qualitaet auf Basis echter Pilotlaeufe. Danach ist die sinnvolle
Reihenfolge:

1. Source-Klassifikation und Jobportal-Denylist implementieren.
2. Query-Templates fuer direkte Ziel-Domains schaerfen.
3. Domain-Qualitaet und SERP-Priorisierung einbauen.
4. LeadEngine-Metriken in CLI/UI sichtbar machen.
5. Danach RatingEngine und Review Queue anhand besserer Targets nachschaerfen.
