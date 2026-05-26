# Security Policy

Target Radar ist ein local-first Tool. Die Standard-UI bindet an `127.0.0.1`
und soll ohne echte Provider-Secrets lauffaehig bleiben.

## Supported Scope

Der aktuelle Open-Source-Vorbereitungsstand unterstuetzt lokale Entwicklung und
lokale Pilotlaeufe. Produktive Mehrbenutzer-Deployments, oeffentliche Server
und gehostete Instanzen sind nicht Ziel dieses Sicherheitsmodells.

## Secrets

- `.env` und `.env.*` duerfen nicht versioniert werden.
- `.env.example` enthaelt nur leere Platzhalter.
- Diagnose-, Provider-Status- und Export-Endpunkte muessen Secrets redigieren.
- Bugreports sollen Diagnoseausgaben aus `/#secrets` nutzen und keine Tokens
  enthalten.

## Local Data

Lokale Datenbanken, Logs, Backups und Exporte liegen unter `data/`, `logs/` und
`exports/`. Diese Pfade sind durch `.gitignore` ausgeschlossen. Vor dem Teilen
von Reports sollte `py -m target_radar.cli privacy-check --root .` laufen.

## Reporting

Sicherheitsprobleme bitte als private Meldung an die Maintainer geben, nicht
als oeffentliches Issue mit Details oder Secrets. Ein minimaler Bericht reicht:

- betroffener Bereich oder Endpunkt
- erwartetes Verhalten
- beobachtetes Verhalten
- redigierte Diagnose aus `/#secrets`, falls relevant

Keine echten API Keys, Datenbanken, Exporte oder personenbezogenen Daten
anhaengen.
