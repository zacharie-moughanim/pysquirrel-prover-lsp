# PySquirrel-prover-LSP

A LSP server for [Squirrel proof assistant](https://squirrel-prover.github.io/), written in Python.

# Features

This is basically a wrapper around `squirrel`'s interactive mode, the main purpose of this server is to prove files rather than commands in the CLI of `squirrel`'s interactive mode.

PySquirrel-prover-LSP allows ongoing proofs on multiple files. Each file is managed in a separate instance of `squirrel`.

## Supported requests

The server supports the following requests:
- `pysquirrellsp/startProof`: starts a proof. Recognized fields (★: mandatory):
  - (★) `id`: a unique identifier for the request (the LSP answers to this command with this `id`).
  - (★) `documentId`: an identifier for the proof, e.g. a path to a .sp file.
  - (★) `pathToSquirrel`: the path to squirrel's executable.

The LSP supports multiple ongoing proofs, so the `documentId` is necessary to perform any actions on a started proof.

- `pysquirrellsp/closeProof`: closes a proof. Recognized fields (★: mandatory):
  - `id`: a unique identifier for the request (the LSP answers to this command with this `id`).
  - (★) `documentId`: an identifier of a previously started proof.
- `pysquirrellsp/proofCommand`: interpret a command on a given ongoing proof. Recognized fields (★: mandatory):
  - (★) `id`: a unique identifier for the request (the LSP answers to this command with this `id`).
  - (★) `documentId`: the identifier of the proof on which the command is interpreted.
  - (★) `proofCommand`: the squirrel command to interpret.
  - `moveCursor`: whether the LSP should add a field `moveCursor` to this command's answer. Current use case is to know whether on interpretation's completion the editor should move the cursor to the end of the proof.

## LSP server answers

### Output

Several messages from the server may answer to a single request of the client. The LSP server signals – with the `id` field – which request is answered and whether the message is the last message answering a given request.

- `pysquirrellsp/squirrelProofOutput`: transmits squirrel's output. Has the following fields (★: always present):
  - (★) `id`: the identifier of the answered request.
  - (★) `documentId`: the identifier of the proof the answer is referring to.
  - (★) `payload`: the message of squirrel (uses Unicode encoding of ANSI color characters).
  - (★) `kind`: the kind of output from squirrel, it can either be:
    - `start`: a message on squirrel's startup;
    - `goal`: describes a proof goal;
    - `warning`: a warning message;
    - `error`: an error message; or
    - `response`: any other message from squirrel.
  - `resetResponses`: if this field is present, hints displayed responses may be cleared.
  - `continuing`: if present, means more messages answering to the corresponding (`id`) request are expected.
  - `commandFailed`: on `pysquirrellsp/proofCommand` response, indicates the command failed.
  - `startSquirrel`: on `pysquirrellsp/startProof` response, indicates a squirrel instance was successfully started.
  - `moveCursor`: this field is present iff it answers a request in which the `moveCursor` field was present.

### Errors

- `pysquirrellsp/lsperror`: an internal LSP server error.
  - (★) `data`: the content of the error message, should be displayed to the user.
  - `failStartup`: if an error occurred during a squirrel's startup, this field contains the corresponding `documentId`.
- `pysquirrellsp/debug`: especially when `DEBUG_MODE` is set to `true`, a debug message.
  - (★) `data`: the content of the debug message.

# Known Issues
- 
