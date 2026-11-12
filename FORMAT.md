# The SCPF Binary Format

This document specifies the binary format of the Starkom Compact Proof Format (SCPF).

SCPF data is the encoding of a protobuf message, the _root message_, according to an SCPF schema.
The format is designed for Ethereum smartcontracts that decode Starkom proofs in place from the
calldata, so it minimizes both the size of the data and the work needed to decode it on the EVM:

- it only contains integers: small integers, field elements, and hashes;
- it has no field tags or field names: the schema determines what comes next;
- it omits every length that the decoder can derive, e.g. from earlier fields;
- it stores repeated 32-byte words only once.

## Overview

SCPF data is made of three consecutive parts:

```
header (64 bytes) || word pool (pool size × 32 bytes) || varint stream
```

- The **header** identifies the data and its layout.
- The **word pool**, or simply **pool**, holds the distinct 32-byte words that the stream refers
  to, e.g. hashes.
- The **varint stream**, or simply **stream**, holds everything else, in the order defined by the
  schema.

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

Every field starts at a multiple of 8 bytes, and the pool starts right after the header, at
offset 64. The reserved bytes leave room for future header fields, which would require a new major
version.

### Versioning

The version numbers in the header are those of the SCPF compiler (the
[`starkom-scpf`](https://pypi.org/project/starkom-scpf/) Python package) that generated the encoder.
The source of truth is `scpf.__version__`.

All the components of the SCPF framework share the same major version number:

- the compiler ([`starkom-scpf`](https://pypi.org/project/starkom-scpf/) on PyPI, developed in the
  `scpf` repository);
- the Rust runtime ([`starkom-scpf-runtime`](https://crates.io/crates/starkom-scpf-runtime) on
  crates.io, developed in the `scpf-runtime` repository), whose major version the generated code
  checks at build time;
- the build-time code generator ([`starkom-scpf-build`](https://crates.io/crates/starkom-scpf-build)
  on crates.io, developed in the `scpf-build` repository), whose version is the version of the
  compiler it embeds;
- the hand-written decoders, e.g. the Solidity ones, which hard-code the version they support.

Decoders must reject data with a different major version number or a higher minor version number,
and ignore the patch version number. Changes that keep older data decodable, e.g. new schema
features, only require a new minor version; all other changes require a new major version.

### Schema identifier

The schema identifier tells apart data encoded with different schemas, or for different root
messages of the same schema, even when the layouts happen to coincide. It's the 32-byte SHA3-256
hash (FIPS 202, not Keccak-256) of the _canonical description_ of the root message. Decoders know
the identifier they expect, so they never need to compute a hash.

The identifier is meant to catch mismatches, not attacks: whoever encodes the data writes the header
too.

The canonical description is a JSON object serialized according to the JSON Canonicalization Scheme
([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)) and encoded in UTF-8. It describes what the
compiler understood from the schema rather than how the schema is written, so comments, formatting,
and the order in which classes are declared don't affect it. It contains:

- `root`: the full name of the protobuf message linked to the root message, e.g.
  `starkom.proto.pcs.v10.Proof`;
- `messages`: the description of the root message and of every message reachable from it through
  its fields, the root message first and then the others in the order in which a depth-first
  traversal of the fields first reaches them. Every message is an object with:
  - `name`: the full name of the linked protobuf message;
  - `fields`: the fields of the message in stream order, each one an object with the `name` of
    the field and its `type` (currently always `varint`).

For example, a schema whose root message is linked to `starkom.proto.pcs.v10.Proof` and has a single
`degree_bound` varint field has this canonical description (exactly these bytes, without any
whitespace):

```
{"messages":[{"fields":[{"name":"degree_bound","type":"varint"}],"name":"starkom.proto.pcs.v10.Proof"}],"root":"starkom.proto.pcs.v10.Proof"}
```

Its SHA3-256 hash, and therefore the schema identifier, is
`0fdfcffe8a5f465181ac34fabdc34ae510b3b3e41941df0b1717190384d1b2a4`.

As the schema language grows, the canonical description will grow with it, following two rules:

- Features are described by keys that are omitted when they're not used, so that new features don't
  change the identifiers of the schemas that don't use them.
- Names that only matter inside the schema, e.g. function parameters, are replaced by their
  positions, so that renaming them doesn't change the identifier. Names that link the schema to
  protobuf messages and fields are kept.

## Pool

The pool is a sequence of `pool size` 32-byte words, which the stream refers to by their position
in the pool (see [Pool references](#pool-references)). It may be empty.

Encoders store every distinct word only once, sorted by decreasing number of references, so that the
most referenced words get the shortest varint indices: the first 128 words take 1 byte, the next
16,256 take 2 bytes, and so on. Words with the same number of references are sorted by the position
of their first reference in the stream.

## Stream

The stream is a sequence of items in the order defined by the schema, with no tags, lengths,
padding, or alignment between them. There are three kinds of items: varints, inline words, and pool
references. The stream ends exactly at the end of the data.

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

An inline word is a fixed-size byte string stored directly in the stream. Its size is determined by
the schema.

A field element is stored as an inline word holding the big-endian representation of its canonical
integer form, in exactly as many bytes as the field requires: 4 for KoalaBear, 8 for Goldilocks,
31 for KoalaBear^8, and 32 for BlueSky, Schraderbrau, and Goldilocks^4.

### Pool references

A pool reference is a varint holding the position of a word in the pool, starting from 0. The value
of the item is the referenced word.

## Decoding

Decoders fail if any of the following checks fails:

- the data starts with the `SCPF` signature;
- the major version number is the one they support, and the minor one is at most theirs;
- all the reserved bytes of the header are 0;
- the schema identifier is the one they expect;
- the pool fits in the data;
- no varint or inline word extends past the end of the data;
- every pool reference is less than the pool size;
- every field element is canonical, i.e. less than the modulus of its field;
- the stream ends exactly at the end of the data.

## Open questions

- **Canonical encodings.** Decoders accept non-minimal varints, pool words that the stream never
  refers to, and pools in any order, so the same message can be encoded in several ways. That's
  harmless for verification, but it means that the encoding of a message isn't unique: hashes of the
  encoded data can't identify a message, and re-encoding decoded data doesn't always reproduce it.
  Decoders could reject non-minimal varints and unreferenced pool words cheaply; checking the order
  of the pool on-chain would be expensive.
- **Pools of other word sizes.** The pool only holds 32-byte words. Pooling smaller words, e.g. the
  field elements of small fields, would need one pool per word size.
