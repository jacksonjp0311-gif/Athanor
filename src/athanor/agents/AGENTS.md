# Agents Subsystem Charter

This document extends the root charter for `src/athanor/agents/`.
See the global charter first:

- `AGENTS.md` (repository root)

## Mission in the loop
Agents operationalize coherence gating:

Telemetry → Propose → Verify → Select → Archive

Each agent should remain focused on a single responsibility so behavior is composable and testable.

## Design principles
- **Single-role clarity**: each module does one stage well.
- **Explicit handoff state**: pass structured candidate data and tags, avoid hidden coupling.
- **Safety-first gating**: verifier semantics must remain transparent (`APPROVE/REFINE/REJECT`).
- **Archive integrity**: admission decisions should remain traceable to measurable descriptors.

## Evolution path for this folder
1. Keep role boundaries explicit.
2. Improve observability at stage boundaries.
3. Add tests for each handoff contract when behavior changes.
4. Expand capabilities only when coherence and reproducibility are preserved.

## Practical map
- `telemetry_agent.py`: trajectory/state capture.
- `proposer_agent.py`: mutation proposal.
- `verifier_agent.py`: coherence gate decisions.
- `selector_agent.py`: score fusion and ranking.
- `archivist_agent.py`: archive admission.

Use `README.md` in this folder for quick orientation and this `AGENTS.md` for contributor intent.
