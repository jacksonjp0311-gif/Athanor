# Experiments Module

This package manages experiment configuration loading and validation.

## Files
- `registry.py` — YAML config loading, inheritance resolution, and guardrail validation.
- `__init__.py` — exports.

## Why this exists
A dedicated loader keeps runtime controls explicit and prevents invalid experiment setups from reaching the loop.
