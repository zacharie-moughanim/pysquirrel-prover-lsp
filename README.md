# PySquirrel-prover-LSP

A LSP server for [Squirrel proof assistant](https://squirrel-prover.github.io/), written in Python.

# Features

This is basically a wrapper around `squirrel`'s interactive mode, the main purpose of this server is to prove files rather than commands in the CLI of `squirrel`'s interactive mode.

PySquirrel-prover-LSP allows ongoing proofs on multiple files. Each file is managed in a separate instance of `squirrel`.

# Known Issues
- `admit` and `Abort` are not highlighted, they appear just as `Qed`.