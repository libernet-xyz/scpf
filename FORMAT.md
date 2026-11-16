# The SCPF Binary Format

This document specifies the binary format of the Starkom Compact Proof Format (SCPF).

SCPF data is the encoding of a protobuf message, the _root message_, e.g. a PLONK proof. The format
defines how the data is framed and how its items are encoded, while the _layout_ of the data, i.e.
which items come in which order, is defined by the encoder of the root message (see
[Layouts](#layouts)).

The format is designed for Ethereum smartcontracts that decode Starkom proofs in place from the
calldata, so it minimizes both the size of the data and the work needed to decode it on the EVM:

- it only contains integers: small integers, field elements, and hashes;
- it has no field tags or field names: the layout determines what comes next;
- it omits everything that the decoder can derive, e.g. lengths that follow from earlier fields or
  from the protocol parameters;
- it stores repeated 32-byte words only once.

SCPF intentionally only supports prime fields of about 256 bits, such as [BlueSky][bluesky],
[Schraderbrau][schraderbrau], and the scalar field of BLS12-381. The EVM is a 256-bit machine and
does arithmetic in these fields natively with its `ADDMOD` and `MULMOD` instructions, and every
element fits in one 32-byte word. Proofs over small fields, e.g. KoalaBear and Goldilocks, would
need extension fields for soundness, and extension field arithmetic would make them much more
expensive to verify.

## Overview

SCPF data is made of three consecutive parts:

```
header (64 bytes) || word pool (pool size × 32 bytes) || varint stream
```

- The **header** identifies the data and its layout.
- The **word pool**, or simply **pool**, holds the distinct 32-byte words that the stream refers to,
  e.g. hashes.
- The **varint stream**, or simply **stream**, holds everything else, in the order defined by the
  layout.

All multi-byte integers are big-endian.

## Header

| Offset | Size | Content                                                                       |
| ------ | ---- | ----------------------------------------------------------------------------- |
| 0      | 4    | Signature: the ASCII characters `SCPF`, i.e. the bytes `0x53 0x43 0x50 0x46`. |
| 4      | 4    | Reserved, must be 0.                                                          |
| 8      | 1    | Major version number.                                                         |
| 9      | 1    | Minor version number.                                                         |
| 10     | 1    | Patch version number.                                                         |
| 11     | 5    | Reserved, must be 0.                                                          |
| 16     | 32   | Schema identifier (see [Schema identifier](#schema-identifier)).              |
| 48     | 4    | Pool size: the number of words in the pool, as an unsigned integer.           |
| 52     | 12   | Reserved, must be 0.                                                          |

The pool starts right after the header, at offset 64. The reserved bytes leave room for future
header fields.

### Versioning

The version numbers in the header are those of the
[`starkom-scpf`](https://crates.io/crates/starkom-scpf) crate that encoded the data, which
implements this format (see its `VERSION` constant). They version the format itself, i.e. the
header, the pool, and the encoding of the items, not the layouts of the root messages, which are
versioned by the [schema identifier](#schema-identifier).

Decoders must reject data with a different major version number, and ignore the minor and patch
version numbers. Every change of the format that existing decoders can't read requires a new major
version of `starkom-scpf`. A minor version can add features to the format, but only new layouts
use them, and new layouts come with new schema identifiers, which existing decoders reject anyway.

The decoders hard-code the major version number they support, e.g. the Solidity decoder of
Starkom's [EVM verifier](https://github.com/libernet-xyz/evm-verifier).

### Schema identifier

The schema identifier tells apart data with different layouts, e.g. proofs of different protocols,
or of incompatible versions of the same protocol. It's the 32-byte Keccak-256 hash of the full name
of the root message encoded in UTF-8. Note that this is Keccak-256 as in Ethereum's `KECCAK256`
instruction, **not** SHA3-256 (FIPS 202).

For example, the root message of a [`starkom-plonk`][starkom-plonk] proof is
`starkom.proto.plonk.v10.Proof`, so its schema identifier is
`keccak256("starkom.proto.plonk.v10.Proof")` =
`781bb0c4b3513d20fb38966e93697ab9c21ea4d2e48cc19ae82d8d00cd1c015e`.

The version component of the protobuf package, e.g. `v10`, changes at the first incompatible change
of the protobuf messages or of the layout, so decoders can tell compatible data apart from
incompatible data by checking the identifier.

The identifier is meant to catch mismatches, not attacks: whoever encodes the data writes the header
too.

## Pool

The pool is a sequence of `pool size` 32-byte words, which the stream refers to by their position in
the pool (see [Pool references](#pool-references)). It may be empty.

Encoders store every distinct word only once, sorted by decreasing number of references, so that the
most referenced words get the shortest pool references: the first 128 words take 1 byte, the next
16,256 take 2 bytes, and so on.

## Stream

The stream is a sequence of items in the order defined by the layout, with no tags, lengths,
padding, or alignment between them. There are three kinds of items: [varints](#varints),
[inline words](#inline-words), and [pool references](#pool-references). The stream ends exactly at
the end of the data.

### Varints

A varint is an unsigned integer of up to 64 bits, encoded in 1 to 9 bytes. The number of leading one
bits of the first byte is the number of bytes that follow it, and the value is stored in big-endian
order in the remaining bits:

| First byte | Total bytes | Value bits |
| ---------- | ----------- | ---------- |
| `0xxxxxxx` | 1           | 7          |
| `10xxxxxx` | 2           | 14         |
| `110xxxxx` | 3           | 21         |
| `1110xxxx` | 4           | 28         |
| `11110xxx` | 5           | 35         |
| `111110xx` | 6           | 42         |
| `1111110x` | 7           | 49         |
| `11111110` | 8           | 56         |
| `11111111` | 9           | 64         |

For example:

| Value    | Encoding                     |
| -------- | ---------------------------- |
| 0        | `00`                         |
| 127      | `7f`                         |
| 128      | `80 80`                      |
| 300      | `81 2c`                      |
| 16,384   | `c0 40 00`                   |
| 2^56     | `ff 01 00 00 00 00 00 00 00` |
| 2^64 - 1 | `ff ff ff ff ff ff ff ff ff` |

Encoders always use the shortest encoding. Decoders also accept longer ones, e.g. `80 01` for 1.

### Inline words

An inline word is a 32-byte word stored directly in the stream rather than in the pool.

A field element is stored as an inline word holding its integer value, which is less than the
modulus of the field. Inline words are stored in big-endian byte order.

### Pool references

A pool reference is a varint holding the position of a word in the pool, starting from 0. The value
of the item is the referenced word.

## Decoding

Decoders must reject the data unless all of the following hold:

- the data must start with the `SCPF` signature;
- the major version number must be the one they support;
- all the reserved bytes of the header must be 0;
- the schema identifier must be the one they expect;
- the pool must fit in the data;
- every varint and inline word must fit in the data;
- every pool reference must be less than the pool size;
- every field element must be canonical, i.e. less than the modulus of its field;
- the stream must end exactly at the end of the data.

## Non-canonical encodings

SCPF is intentionally non-canonical: a message can have many encodings. Encoders minimize the size
of the data as described above, but decoders don't check that they did, so they accept varints
longer than needed, pool words that the stream never refers to or that appear more than once, and
pool words in any order.

Canonical encodings would cost extra gas for verification for no gain. Decoders only need to recover
the message, and a proof is valid or invalid regardless of how it's encoded.

## Layouts

The layout of the data of every root message is defined by its encoder, which pushes the items of
the stream in order to the `Encoder` of the `starkom-scpf` crate and omits everything that the
decoder can derive, e.g. from the protocol parameters, from the circuit, or from the Fiat-Shamir
challenges. The encoders document their layouts:

| Root message                    | Encoder                                                    |
| ------------------------------- | ---------------------------------------------------------- |
| `starkom.proto.plonk.v10.Proof` | [`Proof::to_scpf`][plonk-proof-to-scpf] in `starkom-plonk` |

The PLONK proofs contain a DEEP-FRI proof of `starkom-pcs`, whose FRI commitment and queries are
pushed by [`Proof::encode_scpf_fri_commitment`][pcs-proof-encode-scpf-fri-commitment] and
[`Proof::encode_scpf_queries`][pcs-proof-encode-scpf-queries] in `starkom-pcs`.

[bluesky]: https://crates.io/crates/starkom-bluesky
[pcs-proof-encode-scpf-fri-commitment]: https://docs.rs/starkom-pcs/latest/starkom_pcs/struct.Proof.html#method.encode_scpf_fri_commitment
[pcs-proof-encode-scpf-queries]: https://docs.rs/starkom-pcs/latest/starkom_pcs/struct.Proof.html#method.encode_scpf_queries
[plonk-proof-to-scpf]: https://docs.rs/starkom-plonk/latest/starkom_plonk/struct.Proof.html#method.to_scpf
[schraderbrau]: https://crates.io/crates/starkom-schraderbrau
[starkom-plonk]: https://crates.io/crates/starkom-plonk
