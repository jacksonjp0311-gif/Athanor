# Integration Tests

End-to-end tests for executable paths and run artifact contracts.

## Directory snapshot
```text
tests/integration/
└── test_cli_toy.py
```

## How it works with the system
`test_cli_toy.py` invokes the CLI/module entrypoint with the toy config and asserts output + artifact existence.

> Keep this snapshot updated as integration coverage expands.
