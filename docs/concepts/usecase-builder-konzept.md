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
- Template-Variablen-Mapping
- Priorisierung
- Budget-Defaults
- erlaubte Provider
- optionale Ausschlussbegriffe

Template-Variablen muessen eindeutig auf Felder aus `attribute_schema` zeigen.

MVP-Regel:

- Eine Variable im Template darf exakt einem Feld-Key entsprechen, z. B. `{regions}`.
- Alternativ darf sie ueber `variable_map` auf einen Feld-Key gemappt werden, z. B. `region -> regions`.
- Ohne exakten Feld-Key oder Mapping ist der Use Case ungueltig.
- Listenfelder werden einzeln expandiert. Ein Template mit mehreren Listenfeldern erzeugt ein kontrolliertes kartesisches Produkt.
- Die QueryBuilder-Priorisierung begrenzt die Anzahl gerenderter Kombinationen ueber Budget und Template-Score.
- Spezifische Topic-Templates sollen vor breiten Industrie-Templates stehen.
  Industrie-only Queries sind fuer kleine OSINT-Budgets ein Fallback, weil sie
  sonst fachfremde Firmen trotz korrekter Region in den Lauf ziehen koennen.

Beispiel:

```yaml
query_policy:
  default_template_set: supplier_search
  request_budget_default: 25
  results_per_query_default: 5
  variable_map:
    industry: industries
    product: products
    region: regions
  exclude_terms:
    - jobs
    - stellenangebote
  templates:
    - "{industry} Anbieter {region}"
    - "{product} Hersteller {region}"
    - "{product} Dienstleister {region}"
```

`exclude_terms` werden vom QueryBuilder als negative Suchterme angehaengt, z. B.
`-jobs` oder `-"ranking portal"`. Profil-spezifische `exclude_keywords` werden
zusaetzlich angehaengt. Manuelle Queries bleiben unveraendert.

### `source_policy`

Definiert, welche Quellen gut, neutral, kontextuell oder blockiert sind.

Inhalt:

- bevorzugte Source Types
- kontextuelle Source Types
- blockierte Source Types
- bekannte blockierte Domains
- bekannte bevorzugte Domains
- relevante URL-Pfade
- Listing- und Suchseiten-Tokens
- Import-Schwellen

`context_source_types` sind Quellen, die fuer Evidence und Orientierung nuetzlich sind, aber nicht automatisch als primaere Targets gelten. Beispiele sind Register, Verzeichnisse oder News-Seiten.

MVP-Entscheidung:

`source_policy` konfiguriert den bestehenden `SourceQualityClassifier`. Es werden in Slice U3 keine separaten Policy-Klassen eingefuehrt. Neue Policy-Klassen sind erst sinnvoll, wenn die Konfigurationslogik im bestehenden Classifier zu komplex wird.

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
- Auswertungsart pro Kriterium
- harte Ausschlussregeln
- positive Signale
- Risiken
- Mindestscore fuer Review
- Mindestscore fuer Draft
- LLM-Modus

Rating-Kriterien sind keine magischen Namen.

Jedes Kriterium muss definieren, wie es ausgewertet wird:

- `evaluation: rules`: nutzt ein bekanntes Rule-Set.
- `evaluation: llm`: wird ueber LLM anhand von Evidence und Instruktion bewertet.
- `evaluation: hybrid`: nutzt Rule-Set als Basisscore und LLM fuer Kontextbewertung.

Kriterien koennen zusaetzlich auf bestimmte Evidence Types begrenzt werden:

- `evidence_types`: Liste der zulassigen Evidence Types fuer dieses Kriterium.
- `min_evidence_count`: Mindestanzahl passender Evidence-Objekte.

Wenn `evidence_types` gesetzt ist, bekommt Rule-Set oder LLM nur diese
Evidence als Kontext. Fehlt die Mindestanzahl, wird das Kriterium mit
`missing_required_evidence` markiert, scored `0` und verhindert einen Draft.

Bekannte Evidence Types:

- `target_homepage`
- `target_career`
- `target_contact`
- `target_about`
- `target_page`
- `context_directory`
- `context_news`
- `context_registry`
- `context_repository`
- `context_source`

Bekannte Rule-Sets fuer den MVP:

- `role_keyword_match`
- `tech_keyword_match`
- `region_keyword_match`
- `source_quality`
- `contactability`
- `evidence_quality`

Custom-Keys ohne bekanntes Rule-Set sind nur erlaubt, wenn `evaluation: llm` gesetzt ist und eine kurze `llm_instruction` vorhanden ist.

Jedes Kriterium erzeugt einen Score von `0` bis `100`. Der finale Rating-Score ist die gewichtete Summe:

```text
criterion_score * weight / 100
```

Die Summe aller Gewichte muss im MVP exakt `100` sein.

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
      evaluation: llm
      evidence_types: [target_homepage, target_about, target_contact, context_directory, context_news]
      min_evidence_count: 1
      llm_instruction: "Bewerte, ob das Target fachlich zum Suchprofil passt."
    - key: credibility
      label: Seriositaet
      weight: 30
      evaluation: hybrid
      rule_set: source_quality
      evidence_types: [target_homepage, target_about, target_contact, context_directory, context_registry]
      llm_instruction: "Bewerte, ob die Quelle serioes und direkt genug ist."
    - key: contactability
      label: Kontaktierbarkeit
      weight: 30
      evaluation: rules
      rule_set: contactability
      evidence_types: [target_contact, target_homepage]
      min_evidence_count: 1
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

Bekannte Draft Types fuer den Use Case Builder MVP:

- `application_email`: strukturierter Bewerbungsentwurf.
- `research_summary`: kurze OSINT-/Research-Zusammenfassung.
- `none`: keine automatische Draft-Erzeugung, nur Review.

`research_summary` ist kein Placeholder, sondern bekommt ein eigenes Output-Schema:

```text
title
summary
key_findings
evidence
risks_or_uncertainties
next_steps
```

Validierungsregeln fuer `research_summary`:

- Jede sachliche Kernaussage braucht Evidence-Bezug oder Source-URL.
- Unsichere Aussagen werden als Unsicherheit markiert.
- Keine Kontaktaufnahme, keine Bewerbung, kein Outreach-Text.
- Keine Behauptung ueber interne Fakten ohne Beleg.
- Default-Laenge maximal 2500 Zeichen.

### `review_policy`

Definiert, wie Ergebnisse in der UI erscheinen.

Inhalt:

- Review-Spalten
- sichtbare Score-Komponenten
- erlaubte Aktionen
- Label fuer Entscheidungen
- Feedback-Felder
- Use-Case-Filter und Badge

Beispiel:

```yaml
review_policy:
  default_scope: use_case
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

Wenn mehrere Use Cases aktiv sind, muss die Review Queue Ergebnisse trennen koennen.

MVP-Regel:

- Jedes Review-Item bekommt `use_case_id`, `use_case_name` und `use_case_version`.
- Die UI zeigt mindestens einen Use-Case-Filter und ein Use-Case-Badge pro Ergebnis.
- Die sichtbaren Spalten und Aktionen werden aus der `review_policy` des jeweiligen Use-Case-Snapshots gelesen.
- Die Standardansicht kann alle offenen Items zeigen, muss aber nach Use Case filterbar sein.

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

Template-Rendering:

- Die LeadEngine loest Template-Variablen ueber `query_policy.variable_map` auf.
- Danach muessen alle Variablen auf Felder aus `attribute_schema` zeigen.
- Listenfelder werden einzeln expandiert, nicht als rohe Liste in eine Query geschrieben.
- Fehlende Pflichtfelder verhindern den Lauf.

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

MVP-Auswertung:

- Bekannte Rule-Sets liefern pro Kriterium einen Score von `0` bis `100`.
- LLM-Kriterien bekommen Suchprofil, Evidence, Source-Quality und die `llm_instruction`.
- Hybrid-Kriterien nutzen Rule-Score und LLM-Score gemeinsam; im MVP ist der einfache Merge `max(rule_score, llm_score)`, damit gute harte Signale nicht durch unsichere LLM-Auswertung verloren gehen.
- Wenn ein LLM-Kriterium wegen fehlendem Provider nicht bewertet werden kann, wird das Target nicht automatisch zu `draft`, sondern landet mit Risiko in `review`.

### DraftEngine

Die DraftEngine liest aus dem Use Case:

- `draft_policy`
- Sprache
- Output-Typ
- Pflichtabschnitte
- Sicherheitsregeln

Sie erzeugt keinen generischen Bewerbungstext mehr, wenn der Use Case z. B. `research_summary` verlangt.

Jeder `draft_type` braucht ein bekanntes Output-Schema und eigene Validierungsregeln. Unbekannte Draft Types sind ungueltig.

### Pipeline

Die Pipeline speichert bei jedem Lauf:

- `use_case_id`
- `use_case_version`
- Snapshot der wirksamen Konfiguration

Dadurch bleiben spaetere Bewertungen nachvollziehbar, auch wenn der Use Case danach geaendert wird.

Die Review Queue verwendet ebenfalls den Snapshot. Dadurch kann ein altes Ergebnis noch mit der Policy angezeigt werden, mit der es erzeugt wurde.

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
  created_from_template
  created_at
  updated_at

search_profiles
  use_case_id
  attributes_json

pipeline_runs
  use_case_id
  use_case_version
  use_case_snapshot_json
```

`config_json` enthaelt das validierte Use-Case-Objekt.

`created_from_template` zeigt, welches mitgelieferte Template der Ursprung dieser lokalen Instanz ist.

Moegliche Status:

- `template`
- `active`
- `inactive`
- `archived`

### SQLite-Migration

Die bestehenden Tabellen `search_profiles` und `pipeline_runs` werden nicht neu angelegt.

MVP-Migrationsstrategie:

1. Tabelle `use_cases` anlegen.
2. Default-Template `application_student` einspielen.
3. `ALTER TABLE search_profiles ADD COLUMN use_case_id INTEGER NULL`.
4. `ALTER TABLE search_profiles ADD COLUMN attributes_json TEXT NOT NULL DEFAULT '{}'`.
5. `ALTER TABLE pipeline_runs ADD COLUMN use_case_id INTEGER NULL`.
6. `ALTER TABLE pipeline_runs ADD COLUMN use_case_version INTEGER NULL`.
7. `ALTER TABLE pipeline_runs ADD COLUMN use_case_snapshot_json TEXT NULL`.
8. Bestehende `search_profiles` optional auf `application_student` backfillen.
9. Historische `pipeline_runs` duerfen `NULL` behalten, weil kein Snapshot existiert.

Neue Suchprofile muessen nach der Migration einen Use Case setzen. Fuer alte Profile gilt: Wenn `use_case_id` noch `NULL` ist, nutzt die Anwendung beim Lesen den Default `application_student`.

`search_profiles.attributes_json` speichert use-case-spezifische Eingabefelder wie `topics` oder `industries`, die nicht in den bisherigen Bewerbungsfeldern abgebildet sind. Bestehende Felder wie `roles`, `regions`, `tech_keywords` und `industry_keywords` bleiben erhalten und koennen als Fallback fuer Default-Use-Cases dienen.

SQLite-Hinweis:

`ALTER TABLE ADD COLUMN` ist fuer nullable Spalten ausreichend. Falls spaeter echte Foreign-Key-Constraints oder `NOT NULL` erzwungen werden sollen, braucht SQLite eine Table-Rebuild-Migration. Das ist nicht Teil des ersten MVP.

## 8. Validierung

Ein Use Case ist nur gueltig, wenn:

- `id`, `name` und `version` gesetzt sind,
- mindestens ein Query-Template vorhanden ist,
- Query-Templates nur bekannte Attribute oder Variablen aus `query_policy.variable_map` referenzieren,
- alle Eintraege in `query_policy.variable_map` auf vorhandene `attribute_schema`-Felder zeigen,
- Source Types existieren,
- `preferred_source_types`, `context_source_types` und `blocked_source_types` keine widerspruechlichen Eintraege enthalten,
- Rating-Kriterien eine gueltige `evaluation` haben,
- Rule-Kriterien ein bekanntes `rule_set` referenzieren,
- LLM-Kriterien eine `llm_instruction` haben,
- `evidence_types` nur bekannte Evidence Types enthalten,
- `min_evidence_count` nicht negativ ist,
- Rating-Gewichte exakt zu `100` summieren,
- Draft-Typ bekannt ist,
- Draft-Typ ein bekanntes Output-Schema hat,
- Review-Aktionen erlaubt sind.

Rating-Gewichte muessen fuer den MVP exakt zu `100` summieren.

Beispiel:

```text
relevance 40
credibility 30
contactability 30
= 100
```

Wenn die Summe nicht `100` ist, zeigt die UI einen Fehler. Automatische Normalisierung ist im MVP bewusst nicht vorgesehen, weil die Konfiguration dadurch explizit bleibt.

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
    - key: industry_keywords
      label: Branchen
      type: list
    - key: regions
      label: Regionen
      type: list
query_policy:
  default_template_set: application_student
  request_budget_default: 25
  results_per_query_default: 5
  variable_map:
    role: roles
    tech: tech_keywords
    industry: industry_keywords
    region: regions
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
      evaluation: rules
      rule_set: role_keyword_match
      evidence_types:
        - target_career
        - target_page
      min_evidence_count: 1
    - key: tech_fit
      label: Tech-Fit
      weight: 30
      evaluation: rules
      rule_set: tech_keyword_match
      evidence_types:
        - target_career
        - target_about
        - target_page
      min_evidence_count: 1
    - key: region_fit
      label: Regionaler Fit
      weight: 30
      evaluation: rules
      rule_set: region_keyword_match
      evidence_types:
        - target_career
        - target_contact
        - target_about
        - target_homepage
        - target_page
      min_evidence_count: 1
draft_policy:
  draft_type: application_email
  language: de
  max_length_chars: 3500
review_policy:
  default_scope: use_case
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
  default_template_set: company_osint
  request_budget_default: 25
  results_per_query_default: 5
  variable_map:
    topic: topics
    industry: industries
    region: regions
  exclude_terms:
    - jobs
    - stellenangebote
    - karriere
    - praktikum
    - werkstudent
  templates:
    - "{topic} Unternehmen {region}"
    - "{topic} Kontakt {region}"
    - "{topic} Impressum {region}"
    - "{topic} Services {region}"
    - "{industry} Unternehmen {region}"
    - "{industry} Dienstleister {region}"
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
      evaluation: llm
      evidence_types:
        - target_homepage
        - target_about
        - target_contact
        - target_page
        - context_directory
        - context_news
        - context_registry
        - context_source
      min_evidence_count: 1
      llm_instruction: "Bewerte, ob das Target fachlich zum OSINT-Thema passt."
    - key: credibility
      label: Seriositaet
      weight: 30
      evaluation: hybrid
      rule_set: source_quality
      evidence_types:
        - target_homepage
        - target_about
        - target_contact
        - context_directory
        - context_news
        - context_registry
        - context_source
      llm_instruction: "Bewerte, ob Quelle und Target serioes genug sind."
    - key: evidence_quality
      label: Belegqualitaet
      weight: 30
      evaluation: hybrid
      rule_set: evidence_quality
      evidence_types:
        - target_homepage
        - target_about
        - target_contact
        - target_page
        - context_directory
        - context_news
        - context_registry
        - context_source
      min_evidence_count: 1
      llm_instruction: "Bewerte, ob die gefundenen Belege konkret und belastbar sind."
draft_policy:
  draft_type: research_summary
  language: de
  max_length_chars: 2500
  required_sections:
    - summary
    - key_findings
    - evidence
    - risks_or_uncertainties
review_policy:
  default_scope: use_case
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
- `query_policy.variable_map`
- Rating-Kriterien mit `evaluation`, `rule_set`, `llm_instruction`,
  `evidence_types` und `min_evidence_count`
- bekannte Draft Types `application_email`, `research_summary` und `none`
- Default-Templates als versionierte Dateien oder Python-Konfiguration
- Tests fuer gueltige und ungueltige Use Cases

### Slice U2: Persistenz

Ziel:

Use Cases koennen lokal gespeichert und Suchprofilen zugeordnet werden.

Umfang:

- Tabelle `use_cases`
- `search_profiles.use_case_id`
- Snapshot in `pipeline_runs`
- SQLite-Migration mit nullable Spalten und Default-Use-Case-Fallback
- Tests fuer Laden, Speichern und Snapshot

### Slice U3: LeadEngine-Anbindung

Ziel:

LeadEngine nutzt Query- und Source-Policy aus dem Use Case.

Umfang:

- QueryBuilder liest Templates aus Use Case
- QueryBuilder loest Template-Variablen ueber `variable_map`
- SourceQualityClassifier bekommt Use-Case-Policy als Konfiguration
- bestehender Bewerbungs-Use-Case bleibt Default
- Tests fuer mindestens zwei Use Cases

### Slice U4: Rating- und Draft-Anbindung

Ziel:

RatingEngine und DraftEngine verwenden Use-Case-Policies.

Umfang:

- Rating-Kriterien aus `rating_policy` inklusive `rules`, `llm` und `hybrid`
- bekannte Rule-Sets fuer Bewerbungs- und OSINT-Kriterien
- Draft-Typ aus `draft_policy` inklusive Output-Schema
- LLM-Modus aus Use Case, weiterhin lokal ueberschreibbar
- Validierung fuer `research_summary`
- Tests fuer `application_email` und `research_summary`

### Slice U5: UI-Basis

Ziel:

Nutzer koennen Use Cases sehen, klonen und einem Suchprofil zuweisen.

Umfang:

- Use-Case-Uebersicht
- Detailansicht
- Clone-from-template
- Suchprofil-Auswahl des Use Case
- Review Queue zeigt Use-Case-Badge und Use-Case-Filter

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
- klares Template-Variablen-Mapping
- Query- und Source-Policy konfigurierbar
- bekannte Rule-Sets plus LLM-Kriterien fuer Rating
- `research_summary` als spezifizierter Draft Type
- Suchprofil kann Use Case auswaehlen
- Pipeline speichert Use-Case-Snapshot
- Review Queue kann nach Use Case filtern

Nicht Teil des ersten MVP:

- beliebiger Python-Code
- dynamische Plugin-Ausfuehrung
- komplexe Prompt-Programmierung in der UI
- mehrere Nutzer oder Rechteverwaltung
- Remote-Synchronisation

## 14. Offene Entscheidungen

- Ob Use Cases als YAML-Dateien im Repository oder nur als Datenbankeintraege ausgeliefert werden.
- Wie stark Draft-Policies eigene Prompt-Templates erlauben sollen.
- Ob die Review Queue standardmaessig alle offenen Items zeigt oder den zuletzt aktiven Use Case filtert.
- Ob SQLite-Foreign-Keys fuer `use_case_id` im ersten MVP erzwungen werden oder erst nach einer Table-Rebuild-Migration.

Bereits fuer den MVP entschieden:

- `source_policy` konfiguriert den bestehenden `SourceQualityClassifier`.
- Rating-Kriterien werden hybrid umgesetzt: bekannte Rule-Sets plus LLM-Auswertung fuer Custom-Kriterien.
- Rating-Gewichte muessen exakt zu `100` summieren; die UI normalisiert nicht automatisch.

## 15. Aktueller Stand nach MVP-Umsetzung

Umgesetzt:

- Use-Case-Schema mit Defaults fuer `application_student` und `company_osint`
- lokale Persistenz von Use Cases und Pipeline-Snapshots
- Clone-from-template, Editieren, Import und Export in der lokalen UI
- Suchprofile koennen einem Use Case zugeordnet werden
- LeadEngine nutzt Query- und Source-Policies aus dem Use Case
- RatingEngine und DraftEngine nutzen Use-Case-Policies
- Draft Types `application_email` und `research_summary`
- Review Queue mit Use-Case-Badge und Use-Case-Filter
- UI-Aufteilung in Review, Use Cases, Profile und Runs

Aktuelle Grenzen:

- Die UI startet weiterhin kontrollierte Fake Runs. Echte Provider-Laeufe sind
  aktuell ueber den CLI-Pfad `run-configured` vorbereitet.
- Run-Konfigurationen wie Provider-Modus, Budget, Search Profile und Use Case
  muessen in der UI noch explizit bedienbar werden.
- LLM-Routing soll fuer den lokalen MVP zuerst `light` und `off` sichtbar machen.
  Heavy-Modelle bleiben bewusst optional und werden nicht als naechster
  Umsetzungsschritt vorausgesetzt.
- Der Use-Case-Editor arbeitet noch stark mit JSON-Textfeldern. Fuer dauerhaft
  nutzbare Custom Use Cases braucht er strukturierte Eingaben, Previews und
  klarere Validierungsfehler.
- Import und Export funktionieren konzeptionell, sollen aber als echter
  Datei-Workflow statt nur ueber Textfelder bedienbar werden.
- Review-Feedback wie `reject` und `blacklist` wird noch nicht konsequent als
  lokales Signal fuer spaetere LeadEngine-Laeufe genutzt.
- Provider-Status, Fehler, Kosten-/Request-Zaehler und Qualitaetsmetriken sind
  noch nicht ausreichend in der UI sichtbar.
- Browser-Regressionstests fuer die lokale UI fehlen noch.

Der naechste sinnvolle Produktisierungsschritt ist daher nicht ein weiterer
Use-Case-Typ, sondern die Verbindung der lokalen UI mit echten, begrenzten
Laeufen:

```text
Search Profile waehlen
+ Use Case waehlen
+ Provider-Modus waehlen
+ kleines Budget setzen
+ echten Run starten
+ Evidence, Rating und Draft in der Review Queue pruefen
```

## 16. Zielbild

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
