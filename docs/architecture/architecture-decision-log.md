# Architecture Decision Log

## Zweck

Dieses Dokument haelt zentrale Architekturentscheidungen fest.

Format:

```text
ADR-Nummer
Status
Datum
Entscheidung
Begruendung
Konsequenzen
```

Statuswerte:

- `accepted`
- `superseded`
- `proposed`

## ADR-001: Local-first und Human-in-the-loop

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Target Radar bleibt im MVP eine lokale Anwendung. Es gibt keinen automatischen Versand und keine oeffentliche Server-Komponente.

Begruendung:

- Bewerbungs- und Outreach-Daten koennen personenbezogen oder sensibel sein.
- Lokale Nutzung reduziert Datenschutz- und Betriebsrisiken.
- Der Nutzer soll jede finale Aktion pruefen.

Konsequenzen:

- `.env`, lokale Datenbank, Logs und echte Profile bleiben aus Git ausgeschlossen.
- Drafts bekommen `needs_review`.
- SMTP/automatischer Versand ist nicht Teil des MVP.

## ADR-002: Engines werden getrennt

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

LeadEngine, RatingEngine und DraftEngine sind getrennte fachliche Module.

Begruendung:

- Finden, Bewerten und Formulieren haben unterschiedliche Daten, Fehlerfaelle und Produktlogik.
- Provider-Wechsel in der LeadEngine darf Rating und Drafts nicht beeinflussen.
- Prompt- oder Scoring-Aenderungen sollen isoliert testbar sein.

Konsequenzen:

- LeadEngine kennt keine Drafts.
- RatingEngine kennt keine Suchprovider.
- DraftEngine entscheidet nicht ueber Target-Fit.
- Pipeline-Orchestrator verbindet die Engines.

## ADR-003: Pipeline-Orchestrator besitzt Status-Historie

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Engines schreiben nicht selbst in `target_status_log`. Der Pipeline-Orchestrator oder API-Service persistiert Statuswechsel.

Begruendung:

- Status-Logging muss einheitlich sein.
- Engines sollen Ergebnisobjekte liefern, keine globale Prozesshistorie besitzen.
- API-Einzelaktionen und Pipeline-Laeufe brauchen dieselbe Logging-Regel.

Konsequenzen:

- Engines geben `from_status`, `to_status`, `phase`, `reason` und Fehlerdetails zurueck.
- Orchestrator schreibt aktuellen Target-Status und append-only Log.

## ADR-004: Current Status plus append-only History

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

`targets.status` bleibt der aktuelle Zustand. Eine zusaetzliche Tabelle `target_status_log` haelt Statuswechsel historisch fest.

Begruendung:

- UI braucht einen einfachen aktuellen Status.
- Debugging braucht Historie, z. B. `fetch_failed` -> `fetched`.
- Nutzerentscheidungen sollen nachvollziehbar bleiben.

Konsequenzen:

- Statuswechsel ueberschreiben den aktuellen Target-Status.
- Historie wird nicht ueberschrieben.
- Target-Detailansicht kann Verlauf anzeigen.

## ADR-005: LeadEngine nutzt Query-Fanout statt langer Queries

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Die LeadEngine erzeugt viele kleine Queries aus Templates, statt alle Attribute in eine grosse Query zu pressen.

Begruendung:

- Provider wie Brave haben Query-Limits.
- Lange Queries liefern unscharfe Ergebnisse.
- Kleine Queries lassen sich besser deduplizieren, bewerten und wiederholen.

Konsequenzen:

- `request_budget` wird zentraler Laufparameter.
- Queries erhalten `query_hash`.
- Template-Sets werden pro Profiltyp gewaehlt.

## ADR-006: LeadEngine MVP nutzt `lead_runs` plus bestehende SERP-Tabellen

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Der MVP bekommt `lead_runs` als Laufklammer. `source_queries` und `serp_results` bleiben die Query- und Result-Tabellen und werden erweitert.

Begruendung:

- Run-Status, Budget und Resume brauchen eine eigene Laufklammer.
- Query- und Result-Daten existieren bereits.
- Separate `lead_queries` und `lead_results` waeren im MVP doppelte Struktur.

Konsequenzen:

- `source_queries` bekommt `lead_run_id`, `query_hash`, `query_template`, `template_set`, `query_score`.
- `serp_results` bekommt Lead-Status und Blockgruende.
- Spaetere Extraktion in eigene Lead-Tabellen bleibt moeglich.

## ADR-007: Gemeinsame Rating-Konfiguration

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Score- und Confidence-Schwellenwerte liegen in einer gemeinsamen Rating-Konfiguration und werden von RatingEngine und DraftEngine genutzt.

Begruendung:

- DraftEngine darf keine eigenen abweichenden Score-Schwellen definieren.
- RatingEngine bleibt Quelle der Entscheidung `recommended_action`.
- Gemeinsame Defaults verhindern widerspruechliches Verhalten.

Konsequenzen:

- `min_rule_score_for_ai`, `min_ai_score_for_review`, `min_ai_score_for_draft`, `min_confidence_for_draft` gehoeren in Preset-Konfiguration.
- Suchprofil-Overrides sind spaeter moeglich.
- DraftEngine prueft Schwellen nur defensiv erneut.

## ADR-008: Scores und Drafts werden versioniert und nicht ueberschrieben

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Neue Ratings und neue Drafts erzeugen neue Datensaetze. Alte Scores und Drafts bleiben erhalten.

Begruendung:

- Ergebnisse muessen nachvollziehbar bleiben.
- Prompt- und Regelversionen koennen sich aendern.
- Manuell bearbeitete Drafts duerfen nicht automatisch verloren gehen.

Konsequenzen:

- `target_scores` bekommt `rating_version`.
- `action_drafts` bekommt `draft_version` und optional `regenerated_from_draft_id`.
- Re-Rating und Regeneration sind append-only.

## ADR-009: Page-Kontext wird budgetiert und priorisiert

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

RatingEngine und DraftEngine bekommen nicht alle Page-Texte, sondern einen budgetierten Kontext.

Begruendung:

- LLM-Kontext muss begrenzt und nachvollziehbar sein.
- Karriere-/Job-/Kontaktseiten sind relevanter als beliebige Seiten.
- Input-Snapshots brauchen reproduzierbare Page-Auswahl.

Konsequenzen:

- MVP: maximal 4 Pages, 2.000 Zeichen pro Page, 8.000 Zeichen gesamt.
- RatingEngine priorisiert `career > jobs > about > contact > homepage > other`.
- DraftEngine priorisiert Rating Evidence vor Pages.

## ADR-010: Draft-Sprache ist Nutzerabsicht

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Deutsch ist MVP-Default. Die Target-Sprache stellt Drafts nicht automatisch um.

Begruendung:

- Ein englisches Target kann trotzdem eine deutsche Bewerbung bekommen.
- Sprache ist Nutzerabsicht, nicht reine Seitenerkennung.
- Automatische Sprachwahl kann unerwartetes Verhalten erzeugen.

Konsequenzen:

- Prioritaet: explizite Draft-Sprache > Profilpraeferenz > Preset > Deutsch.
- Spaetere Felder: `profiles.draft_language`, `search_profiles.draft_language`, `drafts.language`.

## ADR-011: Draft-Validierung ist mehrstufig

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Draft-Validierung nutzt deterministische Checks im MVP. Ein LLM-Validator ist spaeter optional.

Begruendung:

- Regex allein ist semantisch schwach.
- Ein LLM-Validator kostet extra und ist fuer den MVP nicht zwingend.
- Human Review bleibt Pflicht.

Konsequenzen:

- MVP: JSON-Schema, Laengen, verbotene klare Muster, Kontext-/Subject-Checks.
- Regex nur fuer eindeutige Muster wie `wie besprochen`.
- Unsichere Drafts bleiben `needs_review`.

## ADR-012: PATCH auf Drafts ist partiell

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

`PATCH /drafts/{id}` aendert nur gesendete Felder.

Begruendung:

- Nutzer kann nur Subject oder Body bearbeiten.
- Nicht gesendete Felder duerfen nicht verloren gehen.
- Bearbeitung soll klar von Regeneration getrennt sein.

Konsequenzen:

- Erlaubte MVP-Felder: `subject`, `body`, `status`.
- `null` bedeutet nicht automatisch loeschen.
- Basisvalidierung laeuft nach Bearbeitung erneut.
- `used_context_json` bleibt unveraendert.

## ADR-013: Review Queue braucht Pagination und Priorisierung

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Die Review Queue wird serverseitig paginiert und standardmaessig nach Relevanz sortiert.

Begruendung:

- 100-200 offene Targets muessen bedienbar bleiben.
- Nutzer soll zuerst die wahrscheinlich wertvollen Targets sehen.
- Bulk-Aktionen brauchen stabile Filter und Auswahl.

Konsequenzen:

- Default: `recommended_action=draft`, dann Score, Confidence, Aktualitaet.
- MVP: Page Size 50, Max 100.
- Filter nach Status, Suchprofil, Quelle, Risiko.

## ADR-014: Konfigurations-Snapshots fuer Nachvollziehbarkeit

Status: `accepted`

Datum: 2026-05-21

Entscheidung:

Lauf-, Score- und Draft-Ergebnisse speichern relevante Konfigurations- und Kontext-Snapshots.

Begruendung:

- Defaults koennen sich aendern.
- Alte Ergebnisse muessen erklaerbar bleiben.
- Debugging braucht die tatsaechlich genutzten Parameter.

Konsequenzen:

- `lead_runs.stats_json` speichert Budget-/Laufwerte.
- `target_scores.input_snapshot_json` speichert Rating-Kontext.
- `action_drafts.used_context_json` speichert Draft-Kontext.

