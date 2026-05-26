# Lokales Setup und Betrieb

## Ziel

Dieses Dokument beschreibt den reproduzierbaren lokalen Betrieb von Target Radar.

Target Radar ist fuer lokale Nutzung und Open Source vorbereitet. Standardmaessig bindet die UI nur an `127.0.0.1`.

## Voraussetzungen

- Python 3.11 oder neuer
- Git
- Windows mit Python Launcher `py` oder Unix/macOS mit `python`

Aktuelle lokale Verifikation wurde mit Python 3.14 ausgefuehrt.

## Installation

Windows:

```powershell
cd C:\Users\Luka\Desktop\target-radar
$env:PYTHONPATH='src'
```

Unix/macOS:

```bash
cd ~/target-radar
export PYTHONPATH=src
```

Optional fuer eine isolierte Umgebung:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e .
```

Unix/macOS:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Konfiguration

```powershell
Copy-Item .env.example .env
```

Echte lokale Werte gehoeren nur in `.env`.

Die lokale UI bietet dafuer die Seite:

```text
http://127.0.0.1:8765/#secrets
```

Die Seite schreibt bekannte Infrastruktur- und Provider-Werte in `.env`.
Vorhandene Secret-Werte werden nicht zurueck an den Browser gesendet. Ein leeres
Secret-Feld bedeutet: bestehenden Wert behalten.

Nicht versionieren:

- `.env`
- lokale SQLite-Datenbanken
- Logs
- echte Profile
- Exporte

Fuer die aktuelle lokale Aufteilung sind diese Variablen relevant:

- `GITHUB_TOKEN`: GitHub-Zugriff fuer spaetere Repo-/Issue-Workflows
- `BRAVE_API_KEY`: Brave Search Discovery
- `OPENAI_API_KEY`: optionaler Cloud-LLM fuer spaeteres Heavy Thinking
- `LLM_HEAVY_PROVIDER=openai`: bleibt konfigurierbar, wird im Default-Rating-Pfad nicht initialisiert
- `LLM_HEAVY_MODEL=gpt-5.5`: spaeteres Heavy-Profil
- `LOCAL_AI_PROVIDER=ollama`
- `LOCAL_AI_MODEL`: Qwen-Modell fuer Light Thinking
- `LLM_LIGHT_PROVIDER=ollama`
- `LLM_LIGHT_MODEL`: Qwen-Modell fuer Light Thinking
- `SEARCH_PROVIDER=brave`, wenn echte Brave-Suche statt Mock genutzt werden soll
- `TARGET_RADAR_SOURCE_BLOCK_THRESHOLD`: Score-Grenze fuer Discovery-Quellen
- `TARGET_RADAR_BLOCKED_SOURCE_DOMAINS`: kommagetrennte lokale Source-Denylist

Konfigurierter Discovery-Lauf:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli run-configured --role "Werkstudent IT" --region Essen --tech Python --request-budget 5
```

`run-configured` nutzt `SEARCH_PROVIDER` und fuer Rating standardmaessig das
Light-Profil (`LLM_LIGHT_PROVIDER`/`LLM_LIGHT_MODEL`). Fuer lokale Tests bleibt
`run-fake` deterministisch.

## Datenbank initialisieren

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 init-db
```

## Erster lokaler Lauf

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 run-fake
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 review-queue
```

Der Fake-Lauf nutzt keine externen Provider und keine API Keys.

## Lokale UI

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 --log-file logs/target-radar.jsonl serve --host 127.0.0.1 --port 8765
```

Browser:

```text
http://127.0.0.1:8765
```

## Diagnose

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 diagnose
```

Die Diagnose prueft:

- Python-Version
- lokale Schreibrechte fuer Datenbank, Logs und Exporte
- SQLite-Schema-Version und Migrationsstatus
- Brave-Key nur dann als blockierend, wenn echte Brave-Suche konfiguriert ist
- Ollama-Erreichbarkeit und ob das Light-Modell installiert ist
- Tabellenzaehler, aktuelle Runs, Review-Queue-Anzahl und lokale Operationen

Sensible Konfigurationswerte werden redigiert. In der UI steht dieselbe
Diagnose unter:

```text
http://127.0.0.1:8765/#secrets
```

Der JSON-Block kann dort fuer Bugreports kopiert werden.

## Migration und Backup

Die lokale SQLite-Datenbank nutzt eine Schema-Version via `PRAGMA user_version`.
Beim Start oder `init-db` werden fehlende Tabellen und Spalten automatisch
angelegt.

Wenn eine bestehende Datei migriert wird, legt Target Radar vor der Migration
ein Backup im Datenbankordner unter `backups/` an, z. B.:

```text
data/backups/target-radar.local.schema-v1.20260526-160000.sqlite3
```

Die Preflight-Diagnose zeigt:

- aktuelle Schema-Version
- erwartete Schema-Version
- Migrationsstatus
- Backup-Verzeichnis
- letztes Backup

## Lokale Datenverwaltung

Unter `/#secrets` gibt es lokale Datenaktionen:

- `Export Data`: schreibt einen secret-freien JSON-Export nach `exports/`
- `Clear Run Data`: exportiert zuerst und loescht danach Laufzeitdaten

`Clear Run Data` entfernt generierte Runs, Targets, SERP-Ergebnisse, Pages,
Evidence, Ratings, Drafts und Statuslogs. Profile, Use Cases und `.env` bleiben
erhalten. Die Aktion wird in `local_operations` protokolliert.

## Engine-Evaluation

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli evaluate
```

Die Evaluation prueft die deterministische Baseline aus
`docs/evaluation/engine-eval-baseline.json`. Sie misst Source-Quality,
Rating-Entscheidungen und Draft-Grounding ohne echte Provider-Secrets.

Lokale Review-Entscheidungen koennen zusaetzlich als ignorierte Fixture
exportiert werden:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 export-review-eval
py -m target_radar.cli evaluate --fixture exports/local-review-eval.json
```

Der Export landet standardmaessig unter `exports/local-review-eval.json` und
wird nicht versioniert.

Fuer Pilotlaeufe kann zusaetzlich ein Run-Report exportiert werden:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 export-run-report --run-id 26 --output exports/sprint16-run-26-report.json
```

Der Report enthaelt Run-Metadaten, Query-Zusammenfassung, Targets,
Review-Backlog und die aktuelle Review-Feedback-Triage. Auch dieser Export
bleibt lokal unter `exports/`.

## Datenschutz-Check

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli privacy-check --root .
```

Der Check prueft:

- lokale Daten oder Secrets in Git,
- notwendige `.gitignore`-Eintraege,
- leere API-Key-Platzhalter in `.env.example`,
- moegliche Secret-Zuweisungen in versionierten Textdateien.

## Budgetgrenzen

Die UI begrenzt echte Provider-Laeufe hart:

- `request_budget <= 100`
- `results_per_query <= 20`
- `max_pages_per_target <= 20`

Unter `/#runs` zeigt die Vorschau vor dem Start die maximale Zahl an Queries,
Suchergebnissen, Fetch-Requests und LLM-Bewertungen. Bei zu hohen Eingaben
antwortet die API mit `400`, statt Werte still zu erhoehen oder zu kappen.

## Tests

```powershell
$env:PYTHONPATH='src'
py -m unittest discover -s tests
py -m compileall src
py -m target_radar.cli evaluate
py -m target_radar.cli privacy-check --root .
node --check src\target_radar\web\static\app.js
git diff --check
```

Die Tests laufen ohne Netzwerk und ohne echte API Keys.

## Typische Fehler

### `No module named target_radar`

`PYTHONPATH` ist nicht gesetzt oder das Paket ist nicht installiert.

Loesung:

```powershell
$env:PYTHONPATH='src'
```

### Port 8765 ist belegt

Einen anderen lokalen Port nutzen:

```powershell
py -m target_radar.cli serve --host 127.0.0.1 --port 8766
```

### Keine Targets in der Review Queue

Zuerst einen Fake-Lauf starten:

```powershell
py -m target_radar.cli run-fake
```

### Privacy-Check meldet lokale Daten

Pruefen, ob echte Laufzeitdateien versehentlich versioniert wurden:

```powershell
git status --short
git ls-files data logs exports
```
