# Engine Evaluation

Die Eval-Suite ist eine kleine deterministische Regression fuer Ergebnisqualitaet.
Sie nutzt keine Provider-Secrets und ruft kein Live-Web ab.

## Baseline

Fixture:

```text
docs/evaluation/engine-eval-baseline.json
```

Umfang:

- 12 Source-Quality-Faelle
- 8 Rating-Faelle
- 4 Draft-Grounding-Faelle

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
