# Target Radar

Target Radar ist ein local-first MVP fuer das Finden, Bewerten und manuelle Pruefen von Targets.

Der aktuelle Stand besteht aus Architektur- und Konzeptdokumenten. Die Verzeichnisstruktur ist fuer eine spaetere Python-basierte Backend-Implementierung mit getrennten Engines vorbereitet.

## Struktur

- `docs/architecture/`: Architekturentscheidungen und ADRs
- `docs/concepts/`: fachliche Konzepte fuer Pipeline, Engines und Konfiguration
- `docs/planning/`: Sprint- und Slice-Planung
- `src/target_radar/`: spaeterer Anwendungscode
- `src/target_radar/engines/`: LeadEngine, RatingEngine und DraftEngine
- `src/target_radar/pipeline/`: Orchestrierung und Statusfluss
- `src/target_radar/config/`: versionierte Produkt-Konfiguration
- `src/target_radar/storage/`: Persistenz- und Datenbankzugriff
- `tests/`: automatisierte Tests
- `scripts/`: lokale Hilfs- und Wartungsskripte
- `data/`: lokale Laufzeitdaten, in Git standardmaessig ausgeschlossen

## Lokale Konfiguration

1. `.env.example` nach `.env` kopieren.
2. Lokale Werte wie API Keys und Datenbank-URL in `.env` eintragen.
3. `.env`, Datenbanken, Logs und echte Profile bleiben ausserhalb von Git.

## Entwicklung

Tests laufen aktuell ohne externe Services:

```powershell
$env:PYTHONPATH='src'
py -m unittest discover -s tests
```

Lokaler CLI-Smoke-Test:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 init-db
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 run-fake
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 review-queue
```

Konfigurierter Provider-Lauf, z. B. mit `SEARCH_PROVIDER=brave`:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 run-configured --role "Werkstudent IT" --region Essen --tech Python --request-budget 5
```

Lokale UI starten:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 serve --host 127.0.0.1 --port 8765
```

Danach im Browser `http://127.0.0.1:8765` oeffnen.

Diagnose und Datenschutz-Check:

```powershell
$env:PYTHONPATH='src'
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 diagnose
py -m target_radar.cli privacy-check --root .
```

Ausfuehrliche lokale Betriebsdoku: `docs/operations/local-setup.md`.

## Git

Das Repository nutzt `main` als Standard-Branch. Vor einem ersten echten Implementierungsschritt sollte der aktuelle Dokumentations- und Strukturstand committed werden.
