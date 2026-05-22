# Use Case Builder Konzept

## 1. Zweck

Target Radar implementiert aktuell einen konkreten Use Case: lokale Suche nach passenden Bewerbungszielen.

Das System soll aber nicht dauerhaft auf Jobportale, Bewerbungen und Karrierepfade festgelegt bleiben. Nutzer sollen eigene Use Cases ueber die lokale UI definieren koennen, ohne Python-Code zu schreiben und ohne die Engines direkt zu veraendern.

Der Use Case Builder beschreibt deshalb einen konfigurierbaren fachlichen Rahmen:

```text
Use Case
  -> Eingabefelder
  -> Query-Strategie
  -> Quellenregeln
  -> Rating-Regeln
  -> Output-Regeln
  -> Review-Verhalten
```

Der bestehende Bewerbungs-Use-Case wird damit nicht entfernt, sondern zum ersten versionierten Default-Use-Case.

## 2. Leitentscheidung

Use Cases werden nicht als freie Plugins mit beliebigem Code umgesetzt.

Stattdessen bestehen sie aus versionierten Konfigurationsobjekten, die von LeadEngine, RatingEngine, DraftEngine und UI interpretiert werden.

Gruende:

- Local-first bleibt einfach betreibbar.
- Open-Source-Nutzer koennen Use Cases exportieren, teilen und importieren.
- Die UI kann Use Cases validieren und erklaeren.
- Engines behalten klare Verantwortlichkeiten.
- Es entsteht kein Sicherheitsproblem durch beliebigen Code in der UI.

Spaeter kann ein Plugin-System ergaenzt werden. Fuer den MVP reicht ein schema-basierter Builder.

## 3. Begriffe

### Use Case

Ein Use Case beschreibt einen fachlichen Such- und Bewertungsmodus.

Beispiele:

- Bewerbungsziele finden
- OSINT zu Unternehmen sammeln
- Lieferanten recherchieren
- lokale Foerderprogramme finden
- Wettbewerber beobachten
- Open-Source-Projekte nach Technologie und Aktivitaet finden

### Use Case Template

Ein versioniertes Ausgangsprofil, das mitgeliefert wird.

Beispiele:

- `application_student`
- `application_general`
- `supplier_osint`
- `company_research`

### Use Case Instance

Eine lokale Kopie oder Anpassung eines Templates.

Diese Instanz gehoert dem Nutzer und kann in der UI bearbeitet werden.

### Search Profile

Ein konkretes Suchprofil nutzt einen Use Case.

Beispiel:

```text
Use Case: application_student
Search Profile: Werkstudent IT Essen
```

## 4. Grundmodell

Ein Use Case besteht aus sechs fachlichen Bloecken.

```text
use_case
  id
  name
  description
  version
  attribute_schema
  query_policy
  source_policy
  rating_policy
  draft_policy
  review_policy
```

### `attribute_schema`

Definiert, welche Eingabefelder die UI fuer diesen Use Case anbietet.

Beispiele:

- Rollenbegriffe
- Technologien
- Branchen
- Regionen
- Ausschlussbegriffe
- Zielgruppe
- Produkttyp
- Organisationsform
- Quellenfokus

Das Schema beschreibt nicht nur Daten, sondern auch UI-Hinweise:

- Label
- Hilfetext
- Feldtyp
- Mehrfachauswahl ja/nein
- Pflichtfeld ja/nein
- Default-Werte

### `query_policy`

Definiert, wie Suchanfragen erzeugt werden.

Inhalt:

- Template-Set
- Query-Templates
- Priorisierung
- Budget-Defaults
- erlaubte Provider
- optionale Ausschlussbegriffe

Beispiel:

```yaml
query_policy:
  default_template_set: supplier_search
  request_budget_default: 25
  results_per_query_default: 5
  templates:
    - "{industry} Anbieter {region}"
    - "{product} Hersteller {region}"
    - "{product} Dienstleister {region}"
```

### `source_policy`

Definiert, welche Quellen gut, neutral, kontextuell oder blockiert sind.

Inhalt:

- bevorzugte Source Types
- blockierte Source Types
- bekannte blockierte Domains
- bekannte bevorzugte Domains
- relevante URL-Pfade
- Listing- und Suchseiten-Tokens
- Import-Schwellen

Beispiel:

```yaml
source_policy:
  preferred_source_types:
    - company_site
    - official_site
  context_source_types:
    - registry
    - directory
    - news
  blocked_source_types:
    - social
  relevant_path_tokens:
    - impressum
    - about
    - kontakt
    - services
    - products
```

### `rating_policy`

Definiert, wonach ein Target bewertet wird.

Inhalt:

- Rating-Kriterien
- Gewichtungen
- harte Ausschlussregeln
- positive Signale
- Risiken
- Mindestscore fuer Review
- Mindestscore fuer Draft
- LLM-Modus

Beispiel:

```yaml
rating_policy:
  llm_mode: light
  min_score_for_review: 50
  min_score_for_draft: 70
  criteria:
    - key: relevance
      label: Fachliche Relevanz
      weight: 40
    - key: credibility
      label: Seriositaet
      weight: 30
    - key: contactability
      label: Kontaktierbarkeit
      weight: 30
```

### `draft_policy`

Definiert, welche Ausgabe erzeugt wird.

Beispiele:

- Bewerbungsmail
- Research Summary
- Lead Brief
- Lieferantenprofil
- Wettbewerbernotiz
- keine Draft-Erzeugung, nur Review

Inhalt:

- Draft-Typ
- Sprache
- Tonalitaet
- Pflichtabschnitte
- verbotene Aussagen
- maximale Laenge
- Quellenhinweise ja/nein

### `review_policy`

Definiert, wie Ergebnisse in der UI erscheinen.

Inhalt:

- Review-Spalten
- sichtbare Score-Komponenten
- erlaubte Aktionen
- Label fuer Entscheidungen
- Feedback-Felder

Beispiel:

```yaml
review_policy:
  actions:
    - approve
    - reject
    - blacklist
  columns:
    - domain
    - source_type
    - score
    - recommended_action
    - main_reason
```

## 5. UI-Konzept

Die UI bekommt einen Bereich `Use Cases`.

### Uebersicht

Die Uebersicht zeigt:

- Name
- Beschreibung
- Template oder lokale Instanz
- Version
- Anzahl Suchprofile
- letzte Nutzung
- aktiv/inaktiv

Aktionen:

- Use Case oeffnen
- Template klonen
- exportieren
- importieren
- deaktivieren

### Builder

Der Builder ist kein freier Code-Editor.

Er besteht aus klaren Tabs:

```text
Basis
Eingabefelder
Queries
Quellen
Rating
Output
Review
Preview
```

Die wichtigsten Nutzerfluesse:

1. Nutzer klont einen bestehenden Use Case.
2. Nutzer passt Namen und Ziel an.
3. Nutzer definiert Eingabefelder.
4. Nutzer bearbeitet Query-Templates.
5. Nutzer setzt Source-Regeln.
6. Nutzer definiert Rating-Kriterien.
7. Nutzer waehlt Output-Typ.
8. Nutzer testet den Use Case mit einem kleinen Preview-Lauf.

### Advanced Editor

Fuer erfahrene Nutzer gibt es optional einen YAML- oder JSON-Editor.

Regeln:

- Editor ist nur eine alternative Ansicht auf dasselbe Schema.
- Speichern ist nur bei erfolgreicher Validierung moeglich.
- Fehler werden mit Pfad angezeigt, z. B. `rating_policy.criteria[1].weight`.
- Kein beliebiger Python-Code.

## 6. Engine-Anbindung

### LeadEngine

Die LeadEngine liest aus dem Use Case:

- `attribute_schema`
- `query_policy`
- `source_policy`

Sie erzeugt Queries aus den Use-Case-Templates, bewertet Quellen nach der Source Policy und speichert die Source-Quality-Metadaten wie bisher.

Wichtig:

Die LeadEngine bleibt eine Such- und Filter-Engine. Sie bewertet keine finale fachliche Passung.

### RatingEngine

Die RatingEngine liest aus dem Use Case:

- `rating_policy`
- relevante Source-Signale
- Evidence-Konfiguration

Sie berechnet weiter eine nachvollziehbare Entscheidung:

```text
skip / review / draft
```

Der Use Case bestimmt, welche Kriterien und Gewichtungen gelten.

### DraftEngine

Die DraftEngine liest aus dem Use Case:

- `draft_policy`
- Sprache
- Output-Typ
- Pflichtabschnitte
- Sicherheitsregeln

Sie erzeugt keinen generischen Bewerbungstext mehr, wenn der Use Case z. B. `research_summary` verlangt.

### Pipeline

Die Pipeline speichert bei jedem Lauf:

- `use_case_id`
- `use_case_version`
- Snapshot der wirksamen Konfiguration

Dadurch bleiben spaetere Bewertungen nachvollziehbar, auch wenn der Use Case danach geaendert wird.

## 7. Datenmodell

MVP-nahe Tabellen:

```text
use_cases
  id
  slug
  name
  description
  version
  status
  config_json
  source_template
  created_at
  updated_at

search_profiles
  use_case_id

pipeline_runs
  use_case_id
  use_case_version
  use_case_snapshot_json
```

`config_json` enthaelt das validierte Use-Case-Objekt.

`source_template` zeigt, ob der Use Case aus einem mitgelieferten Template entstanden ist.

Moegliche Status:

- `template`
- `active`
- `inactive`
- `archived`

## 8. Validierung

Ein Use Case ist nur gueltig, wenn:

- `id`, `name` und `version` gesetzt sind,
- mindestens ein Query-Template vorhanden ist,
- Query-Templates nur bekannte Attribute referenzieren,
- Source Types existieren,
- Rating-Gewichte sinnvoll sind,
- Draft-Typ bekannt ist,
- Review-Aktionen erlaubt sind.

Rating-Gewichte sollten fuer den MVP auf `100` normalisiert werden.

Beispiel:

```text
relevance 40
credibility 30
contactability 30
= 100
```

Wenn die Summe nicht `100` ist, kann die UI entweder normalisieren oder einen Fehler anzeigen. Fuer den MVP ist ein Fehler besser, weil die Konfiguration dadurch explizit bleibt.

## 9. Import und Export

Use Cases sollen als YAML oder JSON exportierbar sein.

Ziele:

- lokale Backups
- Teilen in Open-Source-Repositories
- Review von Konfigurationen per Git
- einfache Migration zwischen Installationen

Import-Regeln:

- Import validiert gegen Schema.
- Bestehende Slugs werden nicht still ueberschrieben.
- Bei Konflikt kann der Nutzer klonen oder ersetzen.
- Secrets sind nicht Teil des Exports.

## 10. Beispiel: Bewerbungs-Use-Case

```yaml
id: application_student
name: Bewerbung Student
version: 1
attribute_schema:
  fields:
    - key: roles
      label: Rollen
      type: list
      required: true
    - key: tech_keywords
      label: Technologien
      type: list
    - key: regions
      label: Regionen
      type: list
query_policy:
  templates:
    - "{role} {region} Karriere"
    - "{role} {tech} {region}"
    - "{role} {industry} {region}"
source_policy:
  preferred_source_types:
    - company_site
    - official_site
  blocked_source_types:
    - job_board
    - social
    - marketplace
rating_policy:
  llm_mode: light
  min_score_for_review: 50
  min_score_for_draft: 70
  criteria:
    - key: role_fit
      label: Rollenfit
      weight: 40
    - key: tech_fit
      label: Tech-Fit
      weight: 30
    - key: region_fit
      label: Regionaler Fit
      weight: 30
draft_policy:
  draft_type: application_email
  language: de
review_policy:
  actions:
    - approve
    - reject
    - blacklist
```

## 11. Beispiel: Allgemeiner OSINT-Use-Case

```yaml
id: company_osint
name: Unternehmens-OSINT
version: 1
attribute_schema:
  fields:
    - key: topics
      label: Themen
      type: list
      required: true
    - key: industries
      label: Branchen
      type: list
    - key: regions
      label: Regionen
      type: list
query_policy:
  templates:
    - "{topic} Unternehmen {region}"
    - "{industry} Anbieter {region}"
    - "{topic} Referenzen {region}"
source_policy:
  preferred_source_types:
    - company_site
    - official_site
  context_source_types:
    - registry
    - directory
    - news
  blocked_source_types:
    - social
rating_policy:
  llm_mode: light
  min_score_for_review: 45
  min_score_for_draft: 65
  criteria:
    - key: relevance
      label: Relevanz
      weight: 40
    - key: credibility
      label: Seriositaet
      weight: 30
    - key: evidence_quality
      label: Belegqualitaet
      weight: 30
draft_policy:
  draft_type: research_summary
  language: de
review_policy:
  actions:
    - approve
    - reject
    - blacklist
```

## 12. Umsetzung in Slices

### Slice U1: Use-Case-Schema

Ziel:

Ein versioniertes Schema beschreibt Use Cases eindeutig.

Umfang:

- Python-Domainmodell fuer Use Cases
- Validierung
- Default-Templates als versionierte Dateien oder Python-Konfiguration
- Tests fuer gueltige und ungueltige Use Cases

### Slice U2: Persistenz

Ziel:

Use Cases koennen lokal gespeichert und Suchprofilen zugeordnet werden.

Umfang:

- Tabelle `use_cases`
- `search_profiles.use_case_id`
- Snapshot in `pipeline_runs`
- Migration
- Tests fuer Laden, Speichern und Snapshot

### Slice U3: LeadEngine-Anbindung

Ziel:

LeadEngine nutzt Query- und Source-Policy aus dem Use Case.

Umfang:

- QueryBuilder liest Templates aus Use Case
- SourceQualityClassifier bekommt Use-Case-Policy
- bestehender Bewerbungs-Use-Case bleibt Default
- Tests fuer mindestens zwei Use Cases

### Slice U4: Rating- und Draft-Anbindung

Ziel:

RatingEngine und DraftEngine verwenden Use-Case-Policies.

Umfang:

- Rating-Kriterien aus `rating_policy`
- Draft-Typ aus `draft_policy`
- LLM-Modus aus Use Case, weiterhin lokal ueberschreibbar
- Tests fuer `application_email` und `research_summary`

### Slice U5: UI-Basis

Ziel:

Nutzer koennen Use Cases sehen, klonen und einem Suchprofil zuweisen.

Umfang:

- Use-Case-Uebersicht
- Detailansicht
- Clone-from-template
- Suchprofil-Auswahl des Use Case

### Slice U6: UI-Builder

Ziel:

Nutzer koennen eigene Use Cases ohne Code konfigurieren.

Umfang:

- Tabs fuer Basis, Eingabefelder, Queries, Quellen, Rating, Output, Review
- Formularvalidierung
- Query Preview
- Source Policy Preview

### Slice U7: Import und Export

Ziel:

Use Cases koennen geteilt und versioniert werden.

Umfang:

- Export als YAML oder JSON
- Import mit Validierung
- Konfliktbehandlung
- Privacy-Check stellt sicher, dass keine Secrets exportiert werden

## 13. MVP-Grenze

Teil des ersten Use Case Builder MVP:

- bestehender Bewerbungs-Use-Case als Template
- mindestens ein zweites Template fuer `company_osint`
- lokale Speicherung
- Clone-from-template
- Query- und Source-Policy konfigurierbar
- Suchprofil kann Use Case auswaehlen
- Pipeline speichert Use-Case-Snapshot

Nicht Teil des ersten MVP:

- beliebiger Python-Code
- dynamische Plugin-Ausfuehrung
- komplexe Prompt-Programmierung in der UI
- mehrere Nutzer oder Rechteverwaltung
- Remote-Synchronisation

## 14. Offene Entscheidungen

- Ob Use Cases als YAML-Dateien im Repository oder nur als Datenbankeintraege ausgeliefert werden.
- Ob `source_policy` den bestehenden SourceQualityClassifier konfiguriert oder spaeter eigene Policy-Klassen erzeugt.
- Ob Rating-Kriterien zuerst regelbasiert oder direkt ueber LLM-Evaluation parametrisiert werden.
- Wie stark Draft-Policies eigene Prompt-Templates erlauben sollen.
- Ob die UI fuer Rating-Gewichte Normalisierung anbietet oder harte `100` erzwingt.

## 15. Zielbild

Target Radar wird dadurch kein Bewerbungswerkzeug mit vielen Sonderfaellen.

Es wird ein lokales Target-Finding- und OSINT-Werkzeug, bei dem der konkrete Use Case konfigurierbar ist:

```text
gleiche Pipeline
+ konfigurierbare Suchlogik
+ konfigurierbare Quellenlogik
+ konfigurierbare Bewertung
+ konfigurierbarer Output
= viele lokale Use Cases ohne Code-Aenderung
```
