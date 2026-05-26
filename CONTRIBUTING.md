# Contributing

Target Radar is local-first. Contributions should keep the default path usable
without provider keys, network access, or hosted infrastructure.

## Setup

```powershell
git clone <repo-url> target-radar
cd target-radar
Copy-Item .env.example .env
$env:PYTHONPATH='src'
py -m pip install -e .
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 init-db
```

Run the UI locally:

```powershell
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 serve --host 127.0.0.1 --port 8765
```

## Quality Gates

Run these before opening a pull request:

```powershell
$env:PYTHONPATH='src'
py -m compileall src
py -m unittest discover -s tests
py -m target_radar.cli evaluate
py -m target_radar.cli privacy-check --root .
node --check src\target_radar\web\static\app.js
git diff --check
```

The standard gates must not require real Brave, OpenAI, Ollama, or other
provider secrets.

## Useful Contributions

- add deterministic eval cases for bad or surprising results
- improve Source Quality, Rating, Draft, and Use Case behavior with tests
- improve local setup docs and error messages
- add importable use-case examples under `examples/use-cases/`
- keep UI changes local, simple, and operable on `127.0.0.1`

## Non-Goals For v0.1

- hosted SaaS deployment
- multi-user accounts or remote auth
- collecting telemetry
- storing provider secrets outside local `.env`
- automatically contacting real people

## Eval Cases

When reporting a poor result, prefer a small anonymized fixture over a long
description. Include:

- target domain pattern, with real names replaced if needed
- source type and expected action
- short evidence snippets, redacted if needed
- actual action and why it was wrong

Do not attach local databases, `.env`, logs with tokens, or full private web
captures.
