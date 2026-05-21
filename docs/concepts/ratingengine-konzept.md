# RatingEngine Konzept

## 1. Zweck

Die RatingEngine bewertet, wie gut ein Target zu einem Profil und Suchprofil passt.

Sie findet keine neuen Targets, laedt keine Webseiten und erzeugt keine Drafts. Sie arbeitet nur mit bereits vorhandenen Daten:

- Profil
- Suchprofil
- Target
- Target Pages
- Lead-Signale
- Denylist-/Blacklist-Kontext

Die Kernfrage der RatingEngine lautet:

```text
Soll dieses Target uebersprungen, geprueft oder fuer einen Draft vorbereitet werden?
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

Die RatingEngine kennt keine Provider wie Brave oder Google. Sie bewertet nur gespeicherte Targets und deren Kontext.

## 3. Inputs

Pflichtkontext:

- `profile`
- `search_profile`
- `target`
- `target_pages`

Optionaler Kontext:

- LeadEngine-Signale
- SERP-Titel und Snippets
- Source-Qualitaet
- bisherige Scores
- Status-Historie
- Nutzerfeedback aus Review Queue

## 4. Outputs

Die RatingEngine erzeugt einen Target Score.

Output-Felder:

- `rule_score`
- `ai_score`
- `confidence`
- `recommended_action`
- `reasons`
- `risks`
- `evidence`
- `model_name`
- `rating_version`
- `status`

Moegliche Aktionen:

- `skip`: Target passt nicht oder ist zu riskant.
- `review`: Target ist unklar und soll manuell geprueft werden.
- `draft`: Target ist gut genug fuer Draft-Erzeugung.

## 5. Bewertungsphasen

Die RatingEngine arbeitet in mehreren Phasen.

```text
Context Check
  -> Rule Rating
  -> Page Context Builder
  -> AI Rating
  -> Evidence Check
  -> Decision Merge
  -> Score speichern
```

## 6. Context Check

Vor jedem Rating prueft die RatingEngine, ob genug Kontext vorhanden ist.

Pruefungen:

- Gibt es ein Profil?
- Gibt es ein Suchprofil?
- Gibt es ein Target?
- Gibt es mindestens eine brauchbare Target Page?
- Ist das Target nicht blacklisted?
- Ist der Textkontext nicht leer?

Wenn der Kontext fehlt:

- kein AI Rating starten,
- Score als `rating_failed` oder `rating_partial` speichern,
- `recommended_action = review` oder `skip`,
- Fehler nachvollziehbar speichern.

## 7. Rule Rating

Rule Rating ist deterministisch und guenstig.

Es bewertet:

- Rollen-Matches
- Tech-Matches
- Branchen-Matches
- Regions-Matches
- Kontakt-Signale
- Ausschlusskeywords
- Source-Qualitaet
- Textmenge und Kontextqualitaet

Beispielsignale:

```text
Rolle gefunden: +25
Tech gefunden: +20
Region gefunden: +15
Kontaktmoeglichkeit gefunden: +10
Ausschlusskeyword gefunden: -50
Jobportal-Domain: skip
```

Rule Rating entscheidet, ob AI Rating sinnvoll ist.

## 8. AI Rating

AI Rating ist optional und wird nur gestartet, wenn Rule Rating genug Relevanz zeigt.

AI Rating nutzt:

- Profilkontext
- Suchprofilkontext
- Target-Metadaten
- komprimierte Page-Texte
- bisherige Rule-Signale
- klare JSON-Schema-Erwartung

AI Rating muss Quellen liefern.

### Page Context Builder

Mehrere Target Pages werden nicht ungefiltert in den AI Call gegeben.

Die RatingEngine nutzt einen Page Context Builder:

```text
Target Pages
  -> erfolgreiche Pages filtern
  -> nach Seitentyp priorisieren
  -> Text pro Page kuerzen
  -> Gesamtbudget einhalten
  -> Input Snapshot speichern
```

MVP-Budget:

- maximal 4 Pages
- maximal 2.000 Zeichen pro Page
- maximal 8.000 Zeichen Page-Kontext gesamt

Priorisierung nach Seitentyp:

```text
career > jobs > about > contact > homepage > other
```

Wenn keine Karriere- oder Jobseite existiert, ist die Homepage erlaubt, aber sie senkt die Kontextqualitaet.

Pro Page werden gespeichert:

- `page_id`
- `url`
- `page_type`
- `title`
- gekuerzter Text
- gefundene Matching-Signale

Der Builder soll bevorzugt Textabschnitte behalten, die Suchprofilbegriffe enthalten. Wenn keine Trefferabschnitte existieren, wird der Anfang des sichtbaren Texts genutzt.

Erlaubte AI-Ausgabe:

```json
{
  "ai_score": 76,
  "confidence": 0.82,
  "recommended_action": "draft",
  "reasons": [
    {
      "text": "Passender Werkstudenten-Kontext.",
      "source_url": "https://example.com/jobs",
      "evidence": "Werkstudent IT im Bereich Softwareentwicklung"
    }
  ],
  "risks": []
}
```

## 9. Evidence Check

Jede positive AI-Begruendung braucht eine Quelle.

Regeln:

- Keine unbelegten Behauptungen.
- Keine erfundenen Ansprechpartner.
- Keine Interpretation ohne Textanker.
- Reasons brauchen `source_url` oder konkreten Page-Kontext.
- Risks duerfen auch ohne starke Quelle genannt werden, wenn sie aus fehlendem Kontext entstehen.

Wenn AI-Ausgabe keine verwertbaren Quellen enthaelt:

- AI Score wird verworfen oder abgewertet,
- Target wird `rating_partial`,
- `recommended_action = review`.

## 10. Decision Merge

Rule Score und AI Score werden nicht blind addiert.

MVP-Entscheidung:

- Rule Rating ist Gatekeeper.
- AI Rating liefert finale qualitative Einschaetzung.
- Ausschlussgruende koennen AI Score ueberstimmen.
- Niedrige Confidence verhindert `draft`.
- Schwellenwerte sind konfigurierbar, aber im MVP preset-global.

Beispiel:

```text
rule_score >= 40 -> AI Rating erlaubt
ai_score >= 70 und confidence >= 0.55 -> draft
ai_score >= 50 -> review
sonst -> skip
```

Harte Stopper:

- Domain blacklisted
- Denylist-Domain
- Recruiting/Zeitarbeit bei Bewerbungs-Preset
- keine brauchbare Seite
- offensichtlicher Profilkonflikt

### Schwellenwert-Konfiguration

Schwellenwerte sollen nicht dauerhaft hardcoded im Service stehen.

MVP-Entscheidung:

- Default-Werte liegen in einer zentralen Rating-Konfiguration pro Preset.
- Das Suchprofil kann spaeter Overrides bekommen.
- Fuer den ersten MVP gibt es keine UI fuer Schwellenwerte.

Beispiel `application`:

```json
{
  "min_rule_score_for_ai": 40,
  "min_ai_score_for_review": 50,
  "min_ai_score_for_draft": 70,
  "min_confidence_for_draft": 0.55,
  "hard_stop_action": "skip"
}
```

Konfigurationsorte:

- kurzfristig: Python-Konfiguration im Preset-Modul
- spaeter: Datenbanktabelle `rating_configs`
- optional: Suchprofil-Overrides fuer erfahrene Nutzer

Prioritaet:

```text
search_profile_override > preset_config > global_default
```

## 11. Rating-Status

Moegliche Status:

- `rating_pending`
- `rule_passed`
- `rule_skipped`
- `ai_pending`
- `ai_passed`
- `rating_partial`
- `rating_failed`
- `needs_review`

Statuswechsel sollen im `target_status_log` dokumentiert werden.

### Status-Log Ownership

MVP-Entscheidung:

- Der zentrale Pipeline-Orchestrator schreibt `target_status_log`.
- Die RatingEngine liefert ein Ergebnisobjekt mit `from_status`, `to_status`, `phase`, `reason` und Fehlerdetails.
- Wenn RatingEngine direkt per API fuer ein einzelnes Target aufgerufen wird, uebernimmt der API-Service die Orchestrator-Rolle und schreibt den Log.
- Bei einzelnen API-Aktionen darf `target_status_log.pipeline_run_id` NULL sein; der Trigger wird dann in `metadata_json` dokumentiert.

Grund:

Die RatingEngine soll fachliche Bewertung liefern, aber keine globale Prozesshistorie besitzen. Das verhindert doppelte Logs und haelt alle Statuswechsel nach demselben Muster.

Regel:

```text
Engine berechnet Ergebnis.
Orchestrator persistiert Statuswechsel und Log.
```

## 12. Fehlerverhalten

Die RatingEngine isoliert Fehler pro Target.

### Fehlender Kontext

Wenn keine brauchbaren Pages existieren:

- kein AI Call,
- Score mit Risiko speichern,
- `recommended_action = review` oder `skip`,
- Target-Status `rating_failed` oder `rating_partial`.

### AI Provider Fehler

Wenn der AI Provider fehlschlaegt:

- Rule Score bleibt erhalten,
- AI-Fehler wird gespeichert,
- Target wird `rating_partial`,
- kein Draft wird automatisch erzeugt.

### Ungueltige AI Antwort

Wenn JSON ungueltig oder Schema falsch ist:

- Antwort verwerfen,
- Fehler speichern,
- Target `rating_partial`,
- `recommended_action = review`.

### Niedrige Confidence

Wenn AI Score hoch, aber Confidence niedrig:

- kein automatischer Draft,
- `recommended_action = review`.

## 13. Confidence

Confidence ist kein reiner AI-Wert und keine reine Engine-Kennzahl.

MVP-Entscheidung:

- Die AI liefert `raw_confidence` im JSON.
- Die RatingEngine validiert und kalibriert daraus `confidence`.
- Gespeichert wird die kalibrierte `confidence`.
- Optional wird `raw_confidence` in `evidence_json` oder `input_snapshot_json` abgelegt.

Kalibrierungsfaktoren:

- Page-Kontextqualitaet
- Anzahl verwertbarer Quellen
- Evidence Check bestanden
- Widersprueche oder Risiken
- ob nur Homepage statt Karriere-/Jobseite vorhanden ist
- ob AI-Ausgabe Schema und Quellen sauber erfuellt

Beispiel:

```text
raw_confidence = 0.82
keine Karriere-Seite gefunden: -0.10
nur eine Quelle: -0.05
final confidence = 0.67
```

Wenn die AI keine Confidence liefert:

- Engine setzt eine konservative Confidence, z. B. `0.4`,
- `recommended_action` maximal `review`.

Wenn Evidence Check fehlschlaegt:

- Confidence wird stark reduziert,
- `recommended_action` maximal `review`.

## 14. Datenmodell

Bestehende Tabelle:

- `target_scores`

MVP-Erweiterungen:

- `rating_version`
- `rating_status`
- `source_quality`
- `raw_confidence`
- `error_type`
- `error_message`
- `evidence_json`
- `input_snapshot_json`

Warum `input_snapshot_json`:

Ratings sollen nachvollziehbar bleiben, auch wenn sich Pages oder Profile spaeter aendern. Der Snapshot muss nicht den gesamten Text speichern, aber die wichtigsten IDs, URLs, Snippets, Page-Auswahl und Parameter.

## 15. Rating-Versionen

Jede Rating-Logik bekommt eine Version.

Beispiele:

- `rules-v1`
- `rules-v1+ai-v1`
- `rules-v2+ai-v1`

Nutzen:

- Scores bleiben vergleichbar.
- Alte Scores koennen als veraltet markiert werden.
- Nach Regelanpassungen kann gezielt neu bewertet werden.

## 16. Re-Rating

Re-Rating wird gezielt gestartet.

Ausloeser:

- Nutzer klickt `Rerate`.
- Target wurde neu gefetcht.
- Suchprofil wurde geaendert.
- Rating-Version wurde geaendert.
- AI Provider war vorher nicht erreichbar.

Regel:

```text
Ein neues Rating erzeugt einen neuen target_scores-Eintrag.
Alte Scores bleiben fuer Nachvollziehbarkeit erhalten.
```

## 17. API-Idee

```text
POST /targets/{id}/rate
POST /targets/{id}/rerate
GET  /targets/{id}/scores
GET  /scores/{id}
```

Optional spaeter:

```text
POST /rating-runs
GET  /rating-runs/{id}
```

Payload fuer gezieltes Re-Rating:

```json
{
  "search_profile_id": 3,
  "force_ai": false,
  "rating_version": "rules-v1+ai-v1"
}
```

## 18. UI-Idee

Die UI soll Scores erklaerbar machen.

Target-Detail:

- aktueller Score
- empfohlene Aktion
- Rule-Signale
- AI-Gruende
- Risiken
- Quellenlinks
- Rating-Version
- Button `Rerate`

Review Queue:

- Score-Spalte
- Confidence-Spalte
- Risiko-Indikator
- Sortierung nach Score und Confidence
- Filter nach `draft`, `review`, `skip`

## 19. Qualitaetsmetriken

Die RatingEngine sollte messbar machen:

- Anzahl bewerteter Targets
- Skip-Quote
- Review-Quote
- Draft-Quote
- AI-Fehlerquote
- Anteil `rating_partial`
- durchschnittliche Confidence
- spaeter: manuelle Akzeptanzrate pro Score-Bereich

Diese Metriken helfen, Regeln und Templates zu verbessern.

## 20. MVP-Scope

Erster umsetzbarer Scope:

- Rule Rating als Gatekeeper
- AI Rating fuer relevante Targets
- Page Context Builder mit Page-Priorisierung und Budget
- preset-globale Rating-Schwellenwerte
- Confidence-Kalibrierung aus AI-Wert und Kontextqualitaet
- Status-Logging ueber Orchestrator
- Quellenpflicht fuer AI-Gruende
- `recommended_action`
- Fehlerstatus pro Target
- neue Scores statt Ueberschreiben
- Re-Rating per Target-Aktion
- einfache UI-Erklaerung mit Gruenden und Risiken

Noch nicht MVP:

- selbstlernende Gewichtung
- komplexe Kalibrierung
- A/B-Testing mehrerer Rating-Versionen
- automatische Modellwahl
- Bulk-Rating mit Hintergrundjobs

## 21. Leitentscheidung

Die RatingEngine ist die fachliche Bewertungsinstanz, aber nicht die finale Entscheidungsinstanz.

Sie priorisiert und begruendet. Die finale Entscheidung bleibt in der Review Queue beim Nutzer.
