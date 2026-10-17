# ATH-B002: Config inheritance dropped nested keys (dict.update instead of deep merge)

This directory is a portable **Bug2Eval** regression case.

## Contract

- **Before snapshot:** expected to fail the verification command.
- **After snapshot:** expected to pass it.
- **Verification:** `python ATH-B002_config_inherit_nested.py`
- **Timeout:** 300 seconds

## Changed files

- Not recorded

## Use

```bash
bug2eval validate .
bug2eval run . --agent-cmd "YOUR_AGENT_COMMAND"
bug2eval pack .
```

The canonical machine-readable contract is `metadata.json`.
