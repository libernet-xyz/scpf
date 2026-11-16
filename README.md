# SCPF

[![CI](https://img.shields.io/github/actions/workflow/status/libernet-xyz/scpf/ci.yml?label=CI)](https://github.com/libernet-xyz/scpf/actions/workflows/ci.yml)
[![crates.io](https://img.shields.io/crates/v/starkom-scpf)](https://crates.io/crates/starkom-scpf)
[![license](https://img.shields.io/crates/l/starkom-scpf)](https://github.com/libernet-xyz/scpf/blob/main/LICENSE)

## Overview

SCPF (Starkom Compact Proof Format) is the binary format of the Starkom proofs sent to EVM
verifiers. It minimizes the gas cost of verification, with regard to both the calldata and the work
needed to decode it.

This crate provides the SCPF [`Encoder`][encoder]. The encoder implements the format: the header,
the pool of distinct 32-byte words, and the encoding of the items of the stream (varints, inline
words, and pool references). The layout of the stream, i.e. which items come in which order, is up
to the caller, which encodes a protobuf message (the _root message_) by pushing its items in order
and omitting everything that the decoder can derive. For example, [`starkom-plonk`][starkom-plonk]
encodes PLONK proofs with [`Proof::to_scpf`][plonk-proof-to-scpf], and [`starkom-pcs`][starkom-pcs]
provides the methods that push the parts of the DEEP-FRI proofs they contain.

SCPF intentionally only supports prime fields of about 256 bits, such as BlueSky, Schraderbrau, and
the scalar field of BLS12-381, whose elements fit in single EVM words.

The binary format is specified in [FORMAT.md](FORMAT.md).

## Usage

```rust
use primitive_types::H256;
use starkom_bluesky::Scalar;
use starkom_scpf::Encoder;

let mut encoder = Encoder::default();
encoder.push_usize(2);
encoder.push_scalars([Scalar::from_const(12), Scalar::from_const(34)]);
encoder.push_hash(H256::repeat_byte(0xaa));

// The type of the root message determines the schema identifier in the header. Any protobuf
// message type implementing `prost::Name` works, e.g. the `Proof` message of `starkom-plonk`.
let data = encoder.finish::<prost_types::Timestamp>();
assert_eq!(&data[0..4], b"SCPF");
```

## Versioning

The version of this crate is the version of the format, and the encoder writes it in the header of
the data (see [`VERSION`][version]). Decoders only check the major version number.

The layouts are versioned separately, by the _schema identifier_ in the header: the Keccak-256 hash
of the full name of the root message, e.g. `starkom.proto.plonk.v10.Proof`. The version component of
the protobuf package (`v10`) changes at the first incompatible change, so decoders can tell
compatible data apart from incompatible data by checking the identifier.

[encoder]: https://docs.rs/starkom-scpf/latest/starkom_scpf/struct.Encoder.html
[plonk-proof-to-scpf]: https://docs.rs/starkom-plonk/latest/starkom_plonk/struct.Proof.html#method.to_scpf
[starkom-pcs]: https://docs.rs/starkom-pcs
[starkom-plonk]: https://docs.rs/starkom-plonk
[version]: https://docs.rs/starkom-scpf/latest/starkom_scpf/constant.VERSION.html
