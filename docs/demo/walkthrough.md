# Local Demo Walkthrough

This walkthrough uses only fake providers and synthetic data. It does not need
Brave, OpenAI, Ollama, or any other real provider secret.

## 1. Start From A Clean Local Setup

```powershell
git clone <repo-url> target-radar
cd target-radar
Copy-Item .env.example .env
$env:PYTHONPATH='src'
py -m pip install -e .
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 init-db
```

## 2. Start The UI

```powershell
py -m target_radar.cli --database-url sqlite:///data/target-radar.local.sqlite3 serve --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765/#dashboard
```

The dashboard shows provider status, open reviews, latest runs and the next
local action.

## 3. Run A Fake Demo

Open `/#runs` and use:

- Provider: `fake`
- LLM: `off` or `light`
- Fetch: `fake`
- Phase: `full`
- Request Budget: `2`
- Results / Query: `1`
- Max Pages: `1`

The preview shows generated queries and the maximum search, fetch and LLM
budget before the run starts.

## 4. Review Results

Open `/#review`.

Use the filters for:

- Use Case
- Run
- Status
- Action
- Source Type
- Risk

Open a target to inspect:

- decision highlights
- rating reasons and risks
- evidence snippets
- draft grounding
- status timeline

## 5. Import Example Use Cases

Open `/#use-cases`, choose Import and load one of:

```text
examples/use-cases/company-osint-demo.json
examples/use-cases/open-source-project-research.json
```

The examples are synthetic and contain no secrets or personal data.

## 6. Optional Real Provider Run

Only after the fake demo works, configure real providers in `/#secrets`:

- `SEARCH_PROVIDER=brave`
- `BRAVE_API_KEY`
- `LLM_LIGHT_PROVIDER=ollama`
- `LLM_LIGHT_MODEL`
- `LOCAL_AI_BASE_URL=http://127.0.0.1:11434`

Keep small budgets for first real runs.
