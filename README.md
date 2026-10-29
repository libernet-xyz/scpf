# SCPF

[![CI](https://img.shields.io/github/actions/workflow/status/libernet-xyz/scpf/ci.yml?label=CI)](https://github.com/libernet-xyz/scpf/actions/workflows/ci.yml)

## Overview

SCPF (Starkom Compact Proof Format) is the binary format of Starkom proofs designed for EVM
verifiers. The format is optimal for sending proofs to a smartcontract with minimal gas expenditure,
with regard to both calldata usage and decoding execution.

This package is the SCPF schema compiler: given a schema describing the layout of a proof, it
generates the Rust code that serializes and deserializes it. The package is both a command line tool
and a Python library. Its only dependency is Google's `protobuf` package, which it uses to read the
protobuf descriptors of the messages that the generated code converts from and to.

> [!NOTE]
> Work in progress: the schema language and the code generator are not there yet.

## Usage

As a command:

```sh
scpf --version
```

or equivalently, without installing the `scpf` command:

```sh
python3 -m scpf --version
```

As a library:

```python
import scpf

print(scpf.__version__)
```

## Development

Python 3.10 or later is required. Set up a virtual environment with an editable install of the
package and the development tools (dependency groups require pip 25.1 or later):

```sh
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --group dev -e .
```

Then:

```sh
.venv/bin/pytest         # run the tests
.venv/bin/ruff format    # format the code
.venv/bin/ruff check     # lint
.venv/bin/mypy           # type-check
```
