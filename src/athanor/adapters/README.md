# Adapters

Adapters provide pluggable proposal strategies for the proposer agent.

## Contents
- `base.py`: abstract adapter interface.
- `local.py`: built-in Gaussian noise adapter (current default).

## Usage
Construct `ProposerAgent` with a custom adapter to override proposal behavior.
