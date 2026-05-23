# DraftEngine Konzept

## 1. Zweck

Die DraftEngine erzeugt Action Drafts fuer Targets, die von der RatingEngine als geeignet bewertet wurden.

Im Bewerbungs-Preset ist das ein Bewerbungs-Mailentwurf. In anderen Presets kann es ein Outreach-Text, Follow-up, Anfrageentwurf oder sonstiger manueller Aktionsvorschlag sein.

Die DraftEngine versendet nichts automatisch.

Kernfrage:

```text
Welcher pruefbare Entwurf hilft dem Nutzer, die naechste manuelle Aktion schneller und sauberer vorzubereiten?
```

## 2. Abgrenzung

```text
LeadEngine   = Finden
Fetcher      = Seiten laden
Extractor    = Text und Signale extrahieren
RatingEngine = Bewerten
DraftEngine  = Formulieren
Review Queue = Entscheiden
```

Die DraftEngine:

- findet keine Targets,
- bewertet keine finale Passung,
- laedt keine Webseiten,
- sendet keine Nachrichten,
- trifft keine finale Nutzerentscheidung.

Sie formuliert nur auf Basis vorhandener, belegbarer Daten.

## 3. Inputs

Pflichtkontext:

- Profil
- Suchprofil
- Target
- aktueller Target Score
- Rating-Gruende und Risiken
- relevante Target Pages
- aktives Preset

Optionaler Kontext:

- LeadEngine-Signale
- Kontakt-E-Mails
- Nutzer-Tonpraeferenz
- vorherige Drafts
- Review-Feedback
- manuell ausgewaehlte Page-Ausschnitte

## 4. Outputs

Die DraftEngine erzeugt einen Action Draft.

Output-Felder:

- `subject`
- `body`
- `status`
- `draft_type`
- `model_name`
- `draft_version`
- `source_score_id`
- `used_context_json`
- `validation_status`
- `validation_errors_json`

MVP-Status:

- `needs_review`
- `edited`
- `approved`
- `rejected`
- `regenerated`
- `draft_failed`

## 5. Erzeugungsbedingungen

Ein Draft darf nur erzeugt werden, wenn:

- ein passender Score existiert,
- `recommended_action = draft`,
- Score und Confidence die Rating-Schwellen erfuellen,
- mindestens eine brauchbare Target Page existiert,
- das Target nicht blacklisted ist,
- der Kontext keine harten Stopper enthaelt.

Wenn eine Bedingung fehlt:

- kein Draft,
- Fehler oder Risiko speichern,
- Target bleibt in `review` oder `draft_failed`.

## 6. Draft-Typen

Der Draft-Typ kommt aus dem aktiven Preset.

MVP:

- `application_email`

Spaeter:

- `sales_outreach_email`
- `follow_up_email`
- `supplier_request`
- `partnership_intro`
- `internal_note`

Draft-Typen bestimmen:

- Ziel des Texts
- Ton
- Laenge
- Pflichtfelder
- verbotene Aussagen
- Validierungsregeln

## 7. Context Builder

Die DraftEngine bekommt nicht den gesamten Datenbestand.

Sie nutzt einen Draft Context Builder:

```text
Profile
  -> SearchProfile
  -> Target
  -> Latest usable Rating
  -> Evidence Pages
  -> Draft Context
```

MVP-Budget:

- maximal 4 Pages
- fuer Research Summaries maximal 4 Evidence-Snippets
- fuer Research Summaries maximal ca. 1.800 Zeichen Evidence-Kontext
- fuer Bewerbungsentwuerfe maximal 1 Evidence-Snippet
- Rating-Gruende und Risiken immer bevorzugen

Priorisierung:

```text
Context Registry > Context News > Context Directory > Kontakt > About > Homepage > Karriere/Jobs > sonstige Pages
```

Wenn die RatingEngine bereits Page-Ausschnitte im `input_snapshot_json` oder `evidence_json` gespeichert hat, soll die DraftEngine diese bevorzugen.

Die Implementierung speichert im Draft-`used_context`, welche Evidence verwendet
wurde:

- `evidence_id`
- `ref`, z. B. `E1`
- `source_url`
- `evidence_type`
- `context_type`
- `priority`
- `evidence_total_chars`
- `evidence_truncated`

Damit sind Drafts reproduzierbarer und lange Seiten koennen die Validierung
nicht mehr durch unbounded Kontext sprengen.

## 8. Belegpflicht

Die DraftEngine darf nur Aussagen nutzen, die durch Kontext belegbar sind.

Research Summaries nutzen deshalb stabile Evidence-Referenzen:

```text
Key Findings
- E1: [context_directory] ...

Evidence
- E1: https://example.com/source
```

Jeder Finding-Eintrag verweist auf eine Evidence-Referenz. Dieselbe Referenz
muss in der Quellenliste auftauchen. Die Validierung prueft bei Research
Summaries, dass alle verwendeten Evidence-Refs und Source-URLs im Body
enthalten sind.

Erlaubt:

- Profilangaben aus dem Nutzerprofil
- Target-Fakten aus geladenen Pages
- Rating-Gruende mit Quellen
- vorsichtige Formulierungen bei schwachem Kontext

Nicht erlaubt:

- erfundene Ansprechpartner
- Behauptung eines vorherigen Kontakts
- konkrete Stellenausschreibung behaupten, wenn sie nicht im Kontext steht
- falsche Rolle aus altem Draft uebernehmen
- nicht belegte Firmenfakten
- automatischen Versand suggerieren

## 9. Draft Prompt

Der Prompt soll strukturiert sein und ein JSON-Objekt erwarten.

MVP-Schema:

```json
{
  "subject": "string, max 120 Zeichen",
  "body": "string, 90-180 Woerter"
}
```

Prompt-Bestandteile:

- `prompt_kind = draft_generation`
- Preset und Draft-Typ
- Profilkontext
- Suchprofilkontext
- Target-Metadaten
- Rating Score
- Reasons und Risks
- Page-Kontext
- Regeln und Verbote
- gewuenschter Ton

## 10. Validierung

Jeder Draft wird vor dem Speichern validiert.

MVP-Entscheidung:

Die Validierung ist mehrstufig.

```text
JSON Schema Check
  -> deterministische Textchecks
  -> Kontext-/Subject-Checks
  -> optional spaeter: LLM Validator
```

Validierungsregeln:

- Antwort ist valides JSON.
- `subject` ist nicht leer und nicht zu lang.
- `body` ist nicht leer und nicht zu lang.
- keine erfundenen Ansprechpartner.
- keine Formulierungen wie `wie besprochen`.
- keine Aussage, dass bereits Kontakt bestand.
- keine harte Behauptung ohne Quellenkontext.
- Subject nutzt die aktuelle Rolle oder den aktuellen Draft-Typ.

Vor der Validierung darf die DraftEngine den Body defensiv kuerzen oder kompakt
neu rendern, wenn der Generator die konfigurierte Maximallaenge ueberschreitet.
Bei `research_summary` muss diese Kuerzung Evidence-Referenzen und
Source-URLs erhalten. Wenn das wegen zu enger Laengenlimits nicht moeglich ist,
bleibt der Draft invalid und meldet `too_long` oder `ungrounded_claim`.

### Deterministische Checks

Deterministische Checks laufen immer.

Sie pruefen:

- JSON-Struktur
- Laengen
- leere Felder
- verbotene Kontaktbehauptungen
- offensichtlich erfundene Anrede
- verbotene Phrasen
- Subject-Rollenbezug

Technik:

- einfache Normalisierung mit Lowercase und Whitespace-Kollaps,
- kleine Regex-Regeln fuer klar erkennbare Muster,
- keine komplexe semantische Entscheidung per Regex.

Validierungsfehler werden nicht nur als Text, sondern als strukturierte Issues
gespeichert. Wichtige Codes:

- `missing_subject`: Subject fehlt.
- `missing_body`: Body fehlt.
- `too_long`: Body ueberschreitet die konfigurierte Maximallaenge.
- `missing_evidence`: fuer den Draft ist keine Evidence vorhanden.
- `banned_phrase`: global verbotene Phrase gefunden.
- `draft_type_banned_phrase`: Phrase ist fuer diesen Draft-Typ verboten.
- `forbidden_claim`: Use-Case-Policy verbietet diese Aussage.
- `missing_section`: Pflichtabschnitt fehlt.
- `ungrounded_claim`: erforderliche Evidence-Referenz oder Source-URL fehlt.

Beispiele fuer verbotene Muster:

```text
wie besprochen
unser Telefonat
unser Gespraech
vielen Dank fuer das Gespraech
Sehr geehrte Frau <Name>
Sehr geehrter Herr <Name>
```

Regex ist hier nur ein Sicherheitsnetz fuer eindeutige Muster, nicht der Hauptbeweis fuer fachliche Korrektheit.

### Kontext-Checks

Kontext-Checks pruefen einfache, strukturelle Dinge:

- Subject enthaelt aktuelle Zielrolle oder passenden Draft-Typ.
- Draft behauptet keine konkrete Stelle, wenn keine Stelle im Kontext belegt ist.
- Draft nutzt keine alte Rolle aus einem vorherigen Draft.
- Draft spricht nicht von Ansprechpartnern, wenn kein Ansprechpartner im Kontext existiert.

### LLM Validator spaeter

Ein separater LLM Validator kann spaeter ergaenzt werden.

Er soll nicht den Draft erzeugen, sondern pruefen:

- Sind Aussagen durch Kontext belegbar?
- Gibt es unbelegte Firmenbehauptungen?
- Klingt der Text wie automatischer Versand?
- Gibt es Halluzinationen?

MVP:

- kein zusaetzlicher LLM Validator verpflichtend,
- deterministische Checks plus Human Review reichen,
- unsichere Drafts bleiben `needs_review`, nicht `approved`.

Bei Validierungsfehler:

- Draft nicht als `needs_review` speichern,
- Fehler im `target_status_log` speichern,
- strukturierte Codes und Issues in `metadata` erhalten,
- Target auf `draft_failed` oder `rating_partial` lassen,
- Nutzer kann `Regenerate Draft` starten.

## 11. Decision Rules

Die DraftEngine entscheidet nicht, ob ein Target gut ist.

Sie prueft nur, ob ein Draft sicher erzeugbar ist.

MVP-Regeln:

```text
recommended_action muss draft sein
ai_score >= min_ai_score_for_draft
confidence >= min_confidence_for_draft
mindestens eine brauchbare Evidence Page
keine harten Risiken
```

### Gemeinsame Rating-Konfiguration

`min_ai_score_for_draft` und `min_confidence_for_draft` kommen aus derselben Rating-Konfiguration, die auch die RatingEngine fuer den Decision Merge nutzt.

MVP-Entscheidung:

- Die DraftEngine definiert keine eigenen Score-Schwellen.
- Sie liest die aktive `rating_config` fuer Preset und Suchprofil.
- Die RatingEngine bleibt die Quelle der Entscheidung `recommended_action = draft`.
- Die DraftEngine prueft die Schwellen nur defensiv erneut.

Prioritaet:

```text
search_profile_override > preset_config > global_default
```

Beispiel:

```json
{
  "min_ai_score_for_draft": 70,
  "min_confidence_for_draft": 0.55
}
```

Wenn der Score gut ist, aber Context oder Validation schlecht:

- kein Draft,
- `draft_failed`,
- Review Queue zeigt naechsten Schritt, z. B. `Refetch` oder `Rerate`.

## 12. Status-Log Ownership

Die DraftEngine schreibt nicht selbst in `target_status_log`.

MVP-Entscheidung:

- DraftEngine liefert ein Ergebnisobjekt.
- Pipeline-Orchestrator oder API-Service schreibt Statuswechsel und Log.
- DraftEngine liefert Validierungsdetails mit.
- Pipeline-Orchestrator speichert Draft-Fehler mit `draft_error_type`,
  `draft_validation_codes`, `draft_validation_errors` und
  `draft_validation_issues` im `target_status_log`.

Regel:

```text
Engine formuliert.
Orchestrator protokolliert.
Review Queue entscheidet.
```

## 13. Datenmodell

Bestehende Tabelle:

- `action_drafts`

MVP-Erweiterungen:

- `draft_type`
- `draft_version`
- `source_score_id`
- `used_context_json`
- `validation_status`
- `validation_errors_json`
- `generated_by`
- `regenerated_from_draft_id`

Warum `used_context_json`:

Ein Draft muss spaeter nachvollziehbar bleiben, auch wenn Pages, Scores oder Profile geaendert werden. Der Snapshot speichert IDs, URLs, Evidence-Ausschnitte und relevante Parameter, nicht zwingend den gesamten Text.

## 14. Sprache

Drafts brauchen eine klare Sprachentscheidung.

MVP-Entscheidung:

- Default-Sprache ist Deutsch.
- Die Draft-Sprache kommt zuerst aus dem Profil oder Suchprofil, spaeter aus dem Preset.
- Wenn nichts gesetzt ist, nutzt die DraftEngine Deutsch.
- Target-Sprache darf den Draft nicht automatisch umstellen.

Prioritaet:

```text
explicit draft_language > profile language preference > preset default > Deutsch
```

Warum Target-Sprache nicht automatisch gewinnt:

Ein englisches Target kann trotzdem eine deutsche Bewerbung erhalten, wenn der Nutzer das will. Sprache ist Nutzerabsicht, nicht reine Seitenerkennung.

MVP-Felder spaeter:

- `profiles.draft_language`
- `search_profiles.draft_language`
- `drafts.language`

Prompt-Regel:

```text
Schreibe den Draft in draft_language.
Uebersetze keine belegten Eigennamen.
Nutze Profil-Sprachangaben nur als Profilinformation, nicht automatisch als Draft-Sprache.
```

## 15. Draft-Versionen

Jede Draft-Logik bekommt eine Version.

Beispiele:

- `application-email-v1`
- `application-email-v2`
- `sales-outreach-v1`

Nutzen:

- alte Drafts bleiben nachvollziehbar,
- nach Prompt-Aenderungen kann gezielt regeneriert werden,
- Draft-Qualitaet kann nach Version bewertet werden.

## 16. Regeneration

Regeneration erzeugt einen neuen Draft.

Alte Drafts werden nicht ueberschrieben.

Ausloeser:

- Nutzer klickt `Regenerate Draft`.
- Draft wurde abgelehnt.
- Score wurde neu berechnet.
- Target wurde neu gefetcht.
- Profil oder Suchprofil wurde geaendert.
- Draft-Version wurde geaendert.

Regel:

```text
Neuer Draft -> neuer action_drafts-Eintrag
Alter Draft bleibt als Historie erhalten
```

## 17. Bearbeitung durch Nutzer

Nutzer koennen Drafts manuell bearbeiten.

Bearbeitete Drafts bekommen:

- `status = edited`
- `updated_at`
- optional spaeter: Edit-Historie

Die Engine soll manuell bearbeitete Drafts nicht automatisch ueberschreiben.

Wenn ein bearbeiteter Draft regeneriert wird:

- Nutzer muss explizit bestaetigen,
- neuer Draft entsteht separat,
- alter bearbeiteter Draft bleibt erhalten.

### PATCH-Semantik

`PATCH /drafts/{id}` ist partiell.

Nur gesendete Felder werden geaendert.

Erlaubte Felder im MVP:

- `subject`
- `body`
- `status`

Beispiele:

```json
{
  "subject": "Aktualisierter Betreff"
}
```

Der Body bleibt unveraendert.

```json
{
  "body": "Aktualisierter Mailtext"
}
```

Der Subject bleibt unveraendert.

Regeln:

- `null` bedeutet nicht automatisch loeschen.
- Leere Strings sind fuer `subject` und `body` ungueltig.
- Nach jeder Bearbeitung laufen Basisvalidierungen erneut.
- Manuelle Bearbeitung setzt `status = edited`, ausser der Request setzt explizit einen erlaubten Review-Status.
- `used_context_json` wird durch manuelle Bearbeitung nicht veraendert.

Spaeter kann eine Edit-Historie einzelne Feld-Aenderungen speichern.

## 18. Fehlerverhalten

### Fehlender Score

Wenn kein geeigneter Score existiert:

- kein Draft,
- `draft_failed`,
- Fehler `missing_score`.

### Fehlender Kontext

Wenn keine brauchbaren Pages oder Evidence existieren:

- kein Draft,
- Fehler `missing_context`,
- empfohlene Nutzeraktion: `Refetch`.

### LLM Provider Fehler

Wenn der Provider fehlschlaegt:

- kein Draft,
- Fehler `provider_error`,
- Nutzer kann spaeter erneut generieren.

### Ungueltige Antwort

Wenn JSON ungueltig oder Schema falsch ist:

- Antwort verwerfen,
- Fehler `invalid_response`,
- kein `needs_review`.

### Sicherheitsvalidierung fehlgeschlagen

Wenn der Draft verbotene Aussagen enthaelt:

- Draft nicht freigeben,
- Fehler `validation_failed`,
- optional Rohantwort fuer Debugging nur lokal speichern.

## 19. API-Idee

```text
POST /targets/{id}/draft
POST /drafts/{id}/regenerate
GET  /targets/{id}/drafts
GET  /drafts/{id}
PATCH /drafts/{id}
POST /drafts/{id}/approve
POST /drafts/{id}/reject
```

Payload fuer gezielte Draft-Erzeugung:

```json
{
  "search_profile_id": 3,
  "score_id": 42,
  "draft_type": "application_email",
  "draft_version": "application-email-v1",
  "draft_language": "de"
}
```

## 20. UI-Idee

Target-Detail:

- aktueller Draft
- Draft-Historie
- verwendeter Score
- verwendete Evidence
- Sprache
- Button `Regenerate Draft`
- Button `Approve`
- Button `Reject`
- Editor fuer manuelle Anpassung

Review Queue:

- Draft-Vorschau
- Score und Confidence daneben
- Risiko-Indikator
- schnelle Aktionen: `Approve`, `Reject`, `Edit`, `Regenerate`, `Blacklist`

Wichtig:

- Draft ist immer als Entwurf erkennbar.
- Quellen und Score bleiben sichtbar.
- Kein UI-Element suggeriert automatischen Versand.

## 21. Qualitaetsmetriken

Die DraftEngine sollte messbar machen:

- Anzahl erzeugter Drafts
- Draft-Fehlerquote
- Validierungsfehlerquote
- Regeneration-Quote
- Edit-Quote
- Approval-Quote
- Ablehnungsgruende
- Draft-Qualitaet nach Version
- Draft-Qualitaet nach Sprache

Diese Metriken helfen, Prompt und Validierung zu verbessern.

## 22. MVP-Scope

Erster umsetzbarer Scope:

- Draft-Erzeugung nur bei `recommended_action = draft`
- Context Builder mit Page- und Evidence-Priorisierung
- JSON-Schema fuer `subject` und `body`
- deterministische Sicherheitsvalidierung
- gemeinsame Rating-Konfiguration fuer Draft-Schwellen
- Deutsch als Default-Draft-Sprache
- partielle PATCH-Semantik fuer manuelle Bearbeitung
- `needs_review` als Default-Status
- Regeneration als neuer Draft
- keine automatische Nachricht
- UI mit Review und manueller Bearbeitung

Noch nicht MVP:

- SMTP-Versand
- automatische Personalisierung mit Ansprechpartnern
- komplexe Edit-Historie
- LLM-basierter Validator
- automatische Sprachwahl aus Target-Sprache
- A/B-Testing mehrerer Prompt-Versionen
- Bulk-Regeneration
- automatische Versandfreigabe

## 23. Leitentscheidung

Die DraftEngine ist ein Formulierungshelfer, kein Versand- oder Entscheidungssystem.

Sie darf nur belegte, pruefbare Entwuerfe erzeugen. Die finale Verantwortung bleibt immer in der Review Queue beim Nutzer.
