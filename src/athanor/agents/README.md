# Agents Module

Operational roles in ATHANOR's coherence-gated evolution loop.

## Directory snapshot
```text
src/athanor/agents/
├── __init__.py
├── archivist_agent.py
├── base.py
├── proposer_agent.py
├── selector_agent.py
├── telemetry_agent.py
└── verifier_agent.py
```

## What each script does
- `base.py` — shared interface for agent-style components.
- `telemetry_agent.py` — generates trajectory telemetry.
- `proposer_agent.py` — mutates parent candidates.
- `verifier_agent.py` — computes coherence verdicts.
- `selector_agent.py` — computes quality/coherence blended selection score.
- `archivist_agent.py` — archive admission mediation.

## How it works together
Proposer creates change, Telemetry measures it, Verifier gates stability, Selector ranks candidates, Archivist preserves diverse coherent elites.

> Keep this snapshot updated as agent modules evolve.
