# Target Radar

Target Radar ist ein local-first Research-Tool fuer Open-Source- und
OSINT-Workflows. Es erzeugt Suchanfragen, sammelt Targets, bewertet Evidence
regel- und LLM-gestuetzt und legt Ergebnisse in einer lokalen Review UI ab.

Die Anwendung bindet standardmaessig nur an `127.0.0.1`. Secrets, lokale
Datenbanken, Logs und Exporte bleiben ausserhalb von Git.

## Schnellstart

### Windows

```powershell
git clone <repo-url> target-radar
cd target-radar
Copy-Item .env.example .env
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 init-db
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 serve --host 127.0.0.1 --port 8765
```

Danach `http://127.0.0.1:8765` im Browser oeffnen.

### Unix/macOS

```bash
git clone <repo-url> target-radar
cd target-radar
cp .env.example .env
export PYTHONPATH=src
python -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 init-db
python -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 serve --host 127.0.0.1 --port 8765
```

## Optional: virtuelle Umgebung

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

## Betrieb ohne Secrets

Der Mock-Modus funktioniert ohne Provider-Keys:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 run-fake
```

In der UI kann ein Fake Run unter `/#runs` gestartet werden. Unter `/#secrets`
zeigt die Preflight-Diagnose, ob Python, Datenbank, Schreibrechte, Brave,
Ollama und lokale Modelle einsatzbereit sind.

## Echte Provider

Relevante `.env`-Variablen:

- `SEARCH_PROVIDER=mock` fuer lokalen Betrieb ohne Search-Key.
- `SEARCH_PROVIDER=brave` plus `BRAVE_API_KEY` fuer echte Discovery.
- `LLM_LIGHT_PROVIDER=ollama` plus `LLM_LIGHT_MODEL` fuer lokales Light Thinking.
- `LOCAL_AI_BASE_URL=http://127.0.0.1:11434` fuer Ollama.
- `OPENAI_API_KEY`, `LLM_HEAVY_PROVIDER` und `LLM_HEAVY_MODEL` bleiben optional.

Beispiel fuer Ollama:

```powershell
ollama serve
ollama pull qwen3:30b-a3b-q4_K_M
```

## Diagnose

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 diagnose
py -m target_radar.cli privacy-check --root .
```

Die Diagnose ist secret-sicher redigiert. In der UI kann sie unter `/#secrets`
kopiert werden.

## Datenbank, Migration und Backups

SQLite wird automatisch initialisiert und migriert. Vor einer Migration einer
bestehenden Datei legt Target Radar ein lokales Backup unter
`<db-ordner>/backups/` an. Die Preflight-Diagnose zeigt Schema-Version,
Migrationsstatus und das letzte Backup.

Unter `/#secrets` kann lokale Laufzeitdaten exportiert und anschliessend
geloescht werden. Profile, Use Cases und `.env` bleiben dabei erhalten.

## Tests

```powershell
$env:PYTHONPATH='src'
py -m compileall src
py -m unittest discover -s tests
node --check src\target_radar\web\static\app.js
git diff --check
```

## Struktur

- `src/target_radar/`: Anwendungscode
- `src/target_radar/engines/`: LeadEngine, RatingEngine, DraftEngine
- `src/target_radar/pipeline/`: Orchestrierung und Statusfluss
- `src/target_radar/storage/`: SQLite-Schema und Repository
- `src/target_radar/web/static/`: lokale UI
- `docs/`: Konzepte, Architektur, Planung und Betrieb
- `tests/`: automatisierte Regressionstests
