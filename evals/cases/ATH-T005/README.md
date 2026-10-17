# ATH-T005: The 2.5 conservative setting does not transfer to the TSP solver

This directory is a portable **Bug2Eval** regression case.

## Contract

- **Before snapshot:** expected to fail the verification command.
- **After snapshot:** expected to pass it.
- **Verification:** `python verify_config.py`
- **Timeout:** 900 seconds

## Changed files

- Not recorded

## Use

```bash
bug2eval validate .
bug2eval run . --agent-cmd "YOUR_AGENT_COMMAND"
bug2eval pack .
```

The canonical machine-readable contract is `metadata.json`.
