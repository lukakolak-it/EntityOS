# Lokales Setup und Betrieb

## Ziel

Dieses Dokument beschreibt den reproduzierbaren lokalen Betrieb von Target Radar.

Target Radar ist fuer lokale Nutzung und Open Source vorbereitet. Standardmaessig bindet die UI nur an `127.0.0.1`.

## Voraussetzungen

- Windows mit Python Launcher `py`
- Python 3.11 oder neuer
- Git

Aktuelle lokale Verifikation wurde mit Python 3.14 ausgefuehrt.

## Installation

```powershell
cd C:\Users\Luka\Desktop\target-radar
$env:PYTHONPATH='src'
```

Optional fuer eine isolierte Umgebung:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e .
```

## Konfiguration

```powershell
Copy-Item .env.example .env
```

Echte lokale Werte gehoeren nur in `.env`.

Nicht versionieren:

- `.env`
- lokale SQLite-Datenbanken
- Logs
- echte Profile
- Exporte

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

Die Diagnose gibt Tabellenzaehler, aktuelle Runs und Review-Queue-Anzahl aus. Sensible Konfigurationswerte werden redigiert.

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

## Tests

```powershell
$env:PYTHONPATH='src'
py -m unittest discover -s tests
py -m compileall src
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
