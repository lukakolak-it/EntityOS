# Target Radar Konfiguration

## 1. Zweck

Dieses Dokument sammelt gemeinsame Schwellenwerte, Budgets und Default-Entscheidungen, die mehrere Module betreffen.

Es verhindert, dass LeadEngine, RatingEngine, DraftEngine und Pipeline-Bausteine eigene widerspruechliche Werte hardcoden.

## 2. Konfigurationsarten

Es gibt drei Arten von Konfiguration.

### Infrastruktur-Konfiguration

Kommt aus `.env`.

Beispiele:

- API Keys
- Provider-Auswahl
- Ports
- Timeouts
- Datenbank-URL

Diese Werte sind laufzeitnah und koennen lokal geheim sein.

### Produkt-Konfiguration

Beschreibt fachliche Defaults.

Beispiele:

- Rating-Schwellen
- Query-Budgets
- Page-Kontext-Budgets
- Review-Queue-Pagination
- Default-Sprache

Diese Werte sollen versioniert und im Code nachvollziehbar sein.

### Lauf-Konfiguration

Kommt aus API-Payloads oder UI-Aktionen.

Beispiele:

- `request_budget`
- `results_per_query`
- `mode`
- `template_set`
- `phases`
- `auto_import`

Diese Werte gelten nur fuer einen konkreten Lauf.

## 3. Prioritaetsregel

Konfiguration wird in dieser Reihenfolge aufgeloest:

```text
explicit run parameter
  > search_profile override
  > preset config
  > global default
```

Secrets und Infrastrukturwerte bleiben davon getrennt:

```text
.env > process environment > code default
```

## 4. MVP-Konfigurationsort

MVP-Entscheidung:

- Infrastrukturwerte bleiben in `.env`.
- Produkt-Konfiguration liegt als Python-Konfiguration im Backend.
- Presets liefern fachliche Defaults.
- Suchprofil-Overrides werden spaeter ergaenzt.
- Eine UI fuer Konfiguration ist nicht Teil des ersten MVP.

Spaeter moeglich:

- `rating_configs`
- `lead_engine_configs`
- `draft_configs`
- UI fuer erfahrene Nutzer

## 5. Gemeinsame Rating-Konfiguration

Diese Werte werden von RatingEngine und DraftEngine gemeinsam genutzt.

MVP-Default fuer Preset `application`:

```json
{
  "min_rule_score_for_ai": 40,
  "min_ai_score_for_review": 50,
  "min_ai_score_for_draft": 70,
  "min_confidence_for_draft": 0.55,
  "fallback_confidence": 0.4,
  "hard_stop_action": "skip"
}
```

Ownership:

- RatingEngine nutzt die Werte fuer Decision Merge.
- DraftEngine nutzt dieselben Werte defensiv vor Draft-Erzeugung.
- Pipeline nutzt `recommended_action`, nicht eigene Score-Logik.

Regel:

```text
DraftEngine darf keine separaten Score-Schwellen definieren.
```

## 6. LeadEngine Budget-Konfiguration

MVP-Defaults:

```json
{
  "request_budget": 100,
  "results_per_query": 10,
  "max_raw_results": 1000,
  "refresh_after_days": 14,
  "default_mode": "focused",
  "default_template_set": "auto"
}
```

Budget-Regeln:

- Jeder gestartete Provider-Request erhoeht `used_budget`.
- Rate-Limit pausiert den Lauf und verbrennt kein weiteres Budget.
- Bereits erfolgreich ausgefuehrte Queries werden per `query_hash` dedupliziert.
- `force=true` darf Dedupe bewusst uebergehen.

### Query Hash

`query_hash` ist der stabile Fingerprint einer konkret ausfuehrbaren Provider-Query.

MVP-Entscheidung:

```text
query_hash = sha256(provider + normalized_query_text + normalized_provider_params)
```

Bestandteile:

- Provider-Name, z. B. `brave`
- final gerenderter Query-Text nach Template-Ersetzung
- providerrelevante Suchparameter, z. B. Land, Sprache, SafeSearch

Nicht enthalten:

- `count` / `results_per_query`
- `request_budget`
- UI-Sortierung
- Lauf-ID
- Zeitstempel

Grund:

Dieselbe Query mit anderer Ergebnisanzahl soll nicht als fachlich neue Query gelten. Dieselbe Query mit anderem Provider oder anderer Suchsprache darf dagegen ein anderer Suchversuch sein.

Normalisierung:

- Whitespace kollabieren
- trimmen
- Query-Text casefolden
- Provider-Parameter nach Key sortieren
- Default-Parameter explizit aufloesen

Beispiel:

```json
{
  "provider": "brave",
  "query": "\"Werkstudentin\" IT Essen Karriere",
  "params": {
    "country": "DE",
    "search_lang": "de",
    "safesearch": "moderate"
  }
}
```

### Refresh-Ausloesung

`refresh_after_days = 14` definiert nur, wann eine bereits erfolgreiche Query wieder als refresh-faehig gilt.

MVP-Entscheidung:

- kein automatischer Hintergrundjob,
- Refresh wird manuell durch den Nutzer gestartet,
- UI-Aktion: `Refresh Discovery`,
- API-Aktion: `POST /pipeline-runs` mit `mode = refresh`.

Spaeter moeglich:

- lokaler Scheduler,
- geplanter Refresh pro Suchprofil,
- Benachrichtigung bei neuen Targets.

## 7. Provider-Konfiguration

MVP:

```json
{
  "default_provider": "brave",
  "mock_provider": "mock",
  "country": "DE",
  "search_lang": "de",
  "ui_lang": "de-DE",
  "safesearch": "moderate"
}
```

Provider-Limits werden provider-spezifisch behandelt.

Brave:

```json
{
  "max_query_chars": 400,
  "max_query_words": 50,
  "max_results_per_request": 20
}
```

Regel:

```text
Provider-Limits werden nicht durch laengere Queries geloest, sondern durch Query-Fanout.
```

## 8. Context-Budget-Konfiguration

RatingEngine und DraftEngine nutzen beide Page-Kontexte.

MVP-Defaults:

```json
{
  "max_context_pages": 4,
  "max_chars_per_page": 2000,
  "max_total_page_chars": 8000
}
```

RatingEngine-Prioritaet:

```text
career > jobs > about > contact > homepage > other
```

DraftEngine-Prioritaet:

```text
Rating Evidence > Karriere/Jobs > Kontakt > About > Homepage > sonstige Pages
```

Die Prioritaeten sind bewusst unterschiedlich.

Begruendung:

- RatingEngine braucht zuerst fachliche Firmen- und Rolleninformationen. Deshalb kommt `about` vor `contact`.
- DraftEngine braucht zuerst belegte Rating-Evidence und danach Kontakt-/Ansprachekontext. Deshalb kommt `Kontakt` vor `About`.

Regel:

```text
Diese Reihenfolgen nicht unreflektiert vereinheitlichen.
```

Snapshot-Regel:

```text
Kontext-Auswahl wird im input_snapshot_json oder used_context_json nachvollziehbar gespeichert.
```

## 9. Fetch-Konfiguration

MVP-Defaults:

```json
{
  "fetch_max_pages_per_domain": 8,
  "fetch_timeout_seconds": 10
}
```

Diese Werte sind aktuell Infrastruktur-nahe Defaults und duerfen aus `.env` kommen.

Produktregel:

```text
Fetcher bleibt shallow. Keine unkontrollierte Tiefensuche.
```

## 10. Review-Queue-Konfiguration

MVP-Defaults:

```json
{
  "default_page_size": 50,
  "max_page_size": 100,
  "default_sort": ["recommended_action", "ai_score", "confidence", "updated_at"]
}
```

Default-Priorisierung:

```text
recommended_action = draft zuerst
ai_score absteigend
confidence absteigend
updated_at absteigend
```

Filter:

- Status
- Suchprofil
- Quelle
- Risiko
- recommended_action

## 11. Draft-Konfiguration

MVP-Defaults:

```json
{
  "default_draft_language": "de",
  "max_subject_chars": 120,
  "max_body_chars": 4000,
  "target_body_words_min": 90,
  "target_body_words_max": 180
}
```

Sprachprioritaet:

```text
explicit draft_language > profile.draft_language > preset default > Deutsch
```

`profile.draft_language` ist ein geplantes Profilfeld.

MVP-Entscheidung:

- Solange das Feld noch nicht existiert, gilt `default_draft_language = de`.
- Bei Einfuehrung wird es optional und darf leer bleiben.
- Suchprofil-spezifische Sprache kann spaeter als `search_profiles.draft_language` ergaenzt werden.

Validierungsstrategie:

```text
JSON Schema Check
  -> deterministische Textchecks
  -> Kontext-/Subject-Checks
  -> optional spaeter: LLM Validator
```

## 12. Status- und Logging-Konfiguration

MVP-Entscheidung:

- aktueller Zustand steht auf dem Target.
- Status-Historie steht in `target_status_log`.
- Orchestrator schreibt Status-Logs.
- Engines liefern Ergebnisobjekte, aber besitzen keine globale Prozesshistorie.

Regel:

```text
Engine berechnet.
Orchestrator persistiert Status und Log.
Review Queue entscheidet.
```

## 13. Konfigurations-Snapshot

Jeder relevante Lauf oder Score soll die verwendeten Konfigurationswerte speichern.

Beispiele:

- `lead_runs.stats_json`
- `target_scores.input_snapshot_json`
- `action_drafts.used_context_json`

Ziel:

```text
Spaetere Aenderungen an Defaults duerfen alte Ergebnisse nicht unerklärbar machen.
```

## 14. MVP-Implementierungsregel

Wenn ein Wert von mehr als einem Modul genutzt wird, gehoert er nicht lokal in einen Service.

Er gehoert in eine gemeinsame Konfiguration:

```text
Preset Config
  -> Rating Config
  -> LeadEngine Config
  -> Draft Config
```

Das verhindert unterschiedliche Schwellenwerte fuer Rating und Draft-Erzeugung.
