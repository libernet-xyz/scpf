# Copyright 2026 The Libernet Team
# SPDX-License-Identifier: Apache-2.0

"""The schema compiler of the Starkom Compact Proof Format (SCPF).

SCPF is a compact binary encoding of Starkom proofs that EVM verifiers can decode in place from the
calldata. An SCPF schema describes the layout of a proof, and the compiler generates the Rust code
that serializes and deserializes it.
"""

from scpf.compiler import compile_schema

__all__ = ["compile_schema"]

__version__ = "0.1.0"
