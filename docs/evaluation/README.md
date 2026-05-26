# Engine Evaluation

Die Eval-Suite ist eine kleine deterministische Regression fuer Ergebnisqualitaet.
Sie nutzt keine Provider-Secrets und ruft kein Live-Web ab.

## Baseline

Fixture:

```text
docs/evaluation/engine-eval-baseline.json
```

Umfang:

- 20 Source-Quality-Faelle
- 22 Rating-Faelle
- 9 Draft-Grounding-Faelle

Die Baseline umfasst damit 51 Faelle und deckt direkte Unternehmensseiten,
Kontextquellen, blockierte Quellen, Use-Case-Rating, AI-Grounding und
Draft-Grounding ab.

Ausfuehrung:

```powershell
py -m target_radar.cli evaluate
```

Optional mit eigener Fixture:

```powershell
py -m target_radar.cli evaluate --fixture docs/evaluation/engine-eval-baseline.json
```

## Interpretation

`accuracy = 1.0` bedeutet nur, dass die aktuelle Engine gegen die festgelegte
Baseline stabil bleibt. Es ist kein Beweis fuer allgemeine Web-Qualitaet.

Wenn ein Fall fehlschlaegt:

- Erwartung pruefen, wenn die Engine absichtlich besser geworden ist.
- Engine fixen, wenn die Erwartung weiterhin fachlich richtig ist.
- Einen neuen Fall ergaenzen, wenn ein echter Run eine neue Fehlerklasse zeigt.

Jeder Fehler enthaelt `section`, `case_id` und `expected_action`, damit ein
CI-Fehler direkt einem Eval-Bereich und einer fachlichen Erwartung zugeordnet
werden kann.

## Lokales Review-Feedback

Lokale UI-Entscheidungen koennen als nicht-versionierte Eval-Fixture exportiert
werden:

```powershell
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 export-review-eval
```

Standardausgabe:

```text
exports/local-review-eval.json
```

Diese Datei bleibt lokal und ist durch `.gitignore` ausgeschlossen. Sie enthaelt
keine Evidence-Texte, sondern nur kompakte Review-/Rating-Metadaten wie Domain,
Review-Status, empfohlene Engine-Aktion, Scores und Evidence-/Draft-Zaehler.

Die lokale Review-Fixture kann direkt gegen den Eval-Runner laufen:

```powershell
py -m target_radar.cli evaluate --fixture exports/local-review-eval.json
```

## Lokaler Run-Report

Fuer Pilotlaeufe kann ein einzelner Pipeline Run als lokaler Report exportiert
werden:

```powershell
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 export-run-report --run-id 26 --output exports/sprint16-run-26-report.json
```

Der Report verbindet:

- Run-Metadaten und Stats
- Query-Liste mit Import-Status-Zaehlern
- Targets mit letzter Run-Bewertung
- offenen Review-Backlog fuer den Run
- aktuelle Review-Feedback-Evaluation und Triage

Der Report ist fuer Sprint-16-Pilotlaeufe gedacht und bleibt unter `exports/`
lokal.

## Review-Feedback-Mapping

- `approved` erwartet `draft`
- `rejected` erwartet `skip`
- `blacklisted` erwartet `skip`

Ein Fehler bedeutet nicht automatisch, dass die Engine falsch ist. Er zeigt
eine Review-Entscheidung, die fachlich geprueft und entweder als neuer
Engine-Fix oder als bewusst abweichender Review-Fall behandelt werden sollte.

Der Eval-Runner triagiert Review-Konflikte automatisch:

- `blacklist_miss`: Review sagt `blacklisted`, Engine sagt nicht `skip`.
- `false_positive_draft`: Review sagt `rejected`, Engine sagt `draft`.
- `false_positive_review`: Review sagt `rejected`, Engine sagt `review`.
- `false_negative`: Review sagt `approved`, Engine sagt nicht `draft`.

Die Ausgabe enthaelt `conflict_summary` und `action_items` mit Severity,
Konflikttyp, Domain und vorgeschlagener naechster Aktion. Diese Einordnung ist
eine Arbeitsliste fuer Heuristik- oder Eval-Fixes, kein automatisches Training.
