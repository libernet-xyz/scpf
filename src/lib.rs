// Copyright 2026 The Libernet Team
// SPDX-License-Identifier: Apache-2.0

#![doc = include_str!("../README.md")]

use primitive_types::{H256, U256};
use sha3::Digest;
use starkom_ff::PrimeField256;
use std::cmp::Reverse;
use std::collections::BTreeMap;

/// The signature at the start of the header: the ASCII characters `SCPF`.
const SIGNATURE: &[u8; 4] = b"SCPF";

/// Parses a part of the version number of the crate at compile time.
///
/// Fails the build if the part doesn't fit in a byte, which is the size of its header field.
const fn parse_version_part(digits: &str) -> u8 {
    match u8::from_str_radix(digits, 10) {
        Ok(part) => part,
        Err(_) => panic!("invalid crate version number"),
    }
}

/// The version of SCPF written in the header: the major, minor, and patch version numbers of this
/// crate.
pub const VERSION: [u8; 3] = [
    parse_version_part(env!("CARGO_PKG_VERSION_MAJOR")),
    parse_version_part(env!("CARGO_PKG_VERSION_MINOR")),
    parse_version_part(env!("CARGO_PKG_VERSION_PATCH")),
];

/// The size of the header in bytes.
const HEADER_SIZE: usize = 64;

/// Returns the schema identifier of SCPF data whose root message is a protobuf message of type `M`:
/// the Keccak-256 hash of the [full name of the message](`prost::Name::full_name`), e.g.
/// `starkom.proto.plonk.v10.Proof`.
///
/// This is the hash of Ethereum's `KECCAK256` instruction rather than SHA3-256 (FIPS 202), so a
/// Solidity decoder can derive the identifier at compile time with `keccak256("...")`.
pub fn schema_identifier<M: prost::Name>() -> H256 {
    let mut hasher = sha3::Keccak256::new();
    hasher.update(M::full_name().as_bytes());
    H256::from_slice(hasher.finalize().as_slice())
}

/// Appends the varint encoding of `value` to `bytes`.
///
/// This function always uses the shortest encoding.
fn push_varint(bytes: &mut Vec<u8>, value: u64) {
    match (1..=8).find(|&length| value >> (7 * length) == 0) {
        Some(length) => {
            let prefix = ((1u64 << (length - 1)) - 1) << (7 * length + 1);
            bytes.extend_from_slice(&(prefix | value).to_be_bytes()[(8 - length)..]);
        }
        None => {
            bytes.push(0xff);
            bytes.extend_from_slice(&value.to_be_bytes());
        }
    }
}

/// An item of the stream.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StreamItem {
    /// An unsigned integer, encoded as a varint.
    Varint(u64),
    /// A 32-byte word stored in the stream.
    InlineWord(U256),
    /// A 32-byte word stored in the pool, encoded in the stream as a pool reference.
    PoolWord(H256),
}

/// Encodes SCPF data.
///
/// Callers push the items of the stream in order and then call [`Self::finish`], which builds the
/// pool and returns the data. The order and the meaning of the items, i.e. the layout of the
/// stream, are defined by the caller, which typically encodes a whole protobuf message (the _root
/// message_) and omits everything that the decoder can derive.
#[derive(Debug, Default)]
pub struct Encoder {
    stream: Vec<StreamItem>,
}

impl Encoder {
    /// Pushes an unsigned integer, encoded as a varint.
    pub fn push_u64(&mut self, value: u64) {
        self.stream.push(StreamItem::Varint(value));
    }

    /// Pushes a `usize`, encoded as a varint.
    pub fn push_usize(&mut self, value: usize) {
        self.push_u64(value as u64);
    }

    /// Pushes a boolean, encoded as a varint: 1 for true and 0 for false.
    pub fn push_bool(&mut self, value: bool) {
        self.push_u64(value.into());
    }

    /// Pushes a field element, encoded as an inline word holding its integer value in big-endian
    /// byte order.
    ///
    /// Only prime fields of about 256 bits are supported, so that every element fits in a word and
    /// EVM verifiers can do arithmetic in the field natively.
    pub fn push_scalar<F: PrimeField256>(&mut self, value: F) {
        self.stream.push(StreamItem::InlineWord(value.to_u256()));
    }

    /// Pushes field elements in order, each one encoded as by [`Self::push_scalar`].
    pub fn push_scalars<F: PrimeField256>(&mut self, values: impl IntoIterator<Item = F>) {
        for value in values {
            self.push_scalar(value);
        }
    }

    /// Pushes a hash, stored in the pool and encoded as a pool reference.
    pub fn push_hash(&mut self, hash: H256) {
        self.stream.push(StreamItem::PoolWord(hash));
    }

    /// Pushes hashes in order, each one encoded as by [`Self::push_hash`].
    pub fn push_hashes(&mut self, hashes: impl IntoIterator<Item = H256>) {
        for hash in hashes {
            self.push_hash(hash);
        }
    }

    /// Returns the SCPF data of a root message of type `M`.
    ///
    /// The header holds [`VERSION`] and the [schema identifier](`schema_identifier`) of `M`.
    ///
    /// The pool holds every distinct word referenced by the stream once, sorted by decreasing
    /// number of references so that the most referenced words get the shortest pool references.
    /// Words with the same number of references are sorted by increasing value.
    ///
    /// Panics if the pool has more than `2^32 - 1` words, which wouldn't fit in the header.
    pub fn finish<M: prost::Name>(self) -> Vec<u8> {
        let mut counts: BTreeMap<H256, usize> = BTreeMap::new();
        for item in &self.stream {
            if let StreamItem::PoolWord(word) = item {
                *counts.entry(*word).or_default() += 1;
            }
        }
        let mut pool: Vec<H256> = counts.keys().copied().collect();
        pool.sort_by_key(|word| Reverse(counts[word]));
        let indices: BTreeMap<H256, usize> = pool
            .iter()
            .enumerate()
            .map(|(index, &word)| (word, index))
            .collect();
        let pool_size = u32::try_from(pool.len()).expect("the SCPF pool is too large");

        let mut data = Vec::with_capacity(HEADER_SIZE + pool.len() * 32);
        data.extend_from_slice(SIGNATURE);
        data.extend_from_slice(&[0u8; 4]);
        data.extend_from_slice(&VERSION);
        data.extend_from_slice(&[0u8; 5]);
        data.extend_from_slice(schema_identifier::<M>().as_bytes());
        data.extend_from_slice(&pool_size.to_be_bytes());
        data.extend_from_slice(&[0u8; 12]);
        for word in &pool {
            data.extend_from_slice(word.as_bytes());
        }
        for item in &self.stream {
            match item {
                StreamItem::Varint(value) => push_varint(&mut data, *value),
                StreamItem::InlineWord(word) => data.extend_from_slice(&word.to_big_endian()),
                StreamItem::PoolWord(word) => push_varint(&mut data, indices[word] as u64),
            }
        }
        data
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use starkom_bluesky::Scalar as BS;
    use starkom_ff::Field;

    /// The root message of the SCPF data of most tests.
    type Root = prost_types::Timestamp;

    fn parse(s: &'static str) -> H256 {
        s.parse().unwrap()
    }

    /// Returns the header of SCPF data with [`Root`] as root message and the given pool size.
    fn header(pool_size: u32) -> Vec<u8> {
        [
            &b"SCPF"[..],
            &[0, 0, 0, 0][..],
            &VERSION[..],
            &[0, 0, 0, 0, 0][..],
            schema_identifier::<Root>().as_bytes(),
            &pool_size.to_be_bytes()[..],
            &[0; 12][..],
        ]
        .concat()
    }

    #[test]
    fn test_version() {
        assert_eq!(VERSION, [1, 0, 0]);
    }

    #[test]
    fn test_schema_identifier() {
        assert_eq!(
            schema_identifier::<prost_types::Timestamp>(),
            parse("0x88ac5a42c1e617f23ca0cd6eecb964171d4c8a8a41a4218a632e990b55fd6915")
        );
    }

    #[test]
    fn test_schema_identifier_of_another_message() {
        assert_eq!(
            schema_identifier::<prost_types::Duration>(),
            parse("0x1fa07945c8fe200d54562b9c80bbdfefaaf6e79fe3b95531b7dd38c4a8709ce4")
        );
    }

    fn test_push_varint_impl(value: u64, expected: &[u8]) {
        let mut output = vec![];
        push_varint(&mut output, value);
        assert_eq!(output, expected);
    }

    #[test]
    fn test_push_varint() {
        test_push_varint_impl(0, &[0x00]);
        test_push_varint_impl(1, &[0x01]);
        test_push_varint_impl(127, &[0x7f]);
        test_push_varint_impl(128, &[0x80, 0x80]);
        test_push_varint_impl(300, &[0x81, 0x2c]);
        test_push_varint_impl(16383, &[0xbf, 0xff]);
        test_push_varint_impl(16384, &[0xc0, 0x40, 0x00]);
        test_push_varint_impl((1 << 21) - 1, &[0xdf, 0xff, 0xff]);
        test_push_varint_impl(1 << 21, &[0xe0, 0x20, 0x00, 0x00]);
        test_push_varint_impl((1 << 28) - 1, &[0xef, 0xff, 0xff, 0xff]);
        test_push_varint_impl(1 << 28, &[0xf0, 0x10, 0x00, 0x00, 0x00]);
        test_push_varint_impl((1 << 35) - 1, &[0xf7, 0xff, 0xff, 0xff, 0xff]);
        test_push_varint_impl(1 << 35, &[0xf8, 0x08, 0x00, 0x00, 0x00, 0x00]);
        test_push_varint_impl((1 << 42) - 1, &[0xfb, 0xff, 0xff, 0xff, 0xff, 0xff]);
        test_push_varint_impl(1 << 42, &[0xfc, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]);
        test_push_varint_impl((1 << 49) - 1, &[0xfd, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]);
        test_push_varint_impl(1 << 49, &[0xfe, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
        test_push_varint_impl(
            (1 << 56) - 1,
            &[0xfe, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff],
        );
        test_push_varint_impl(1 << 56, &[0xff, 0x01, 0, 0, 0, 0, 0, 0, 0]);
        test_push_varint_impl(u64::MAX, &[0xff; 9]);
    }

    #[test]
    fn test_empty_data() {
        let encoder = Encoder::default();
        let data = encoder.finish::<Root>();
        assert_eq!(data, header(0));
    }

    #[test]
    fn test_schema_identifier_in_header() {
        let encoder = Encoder::default();
        let data = encoder.finish::<prost_types::Duration>();
        assert_eq!(
            &data[16..48],
            schema_identifier::<prost_types::Duration>().as_bytes()
        );
    }

    #[test]
    fn test_varints() {
        let mut encoder = Encoder::default();
        encoder.push_u64(300);
        encoder.push_usize(7);
        encoder.push_bool(true);
        encoder.push_bool(false);
        encoder.push_u64(u64::MAX);
        let data = encoder.finish::<Root>();
        assert_eq!(
            data,
            [
                &header(0)[..],
                &[0x81, 0x2c, 0x07, 0x01, 0x00][..],
                &[0xff; 9][..],
            ]
            .concat()
        );
    }

    #[test]
    fn test_scalars() {
        let mut encoder = Encoder::default();
        encoder.push_scalar(BS::from_const(0x1234));
        encoder.push_scalars([BS::ZERO, -BS::ONE]);
        let data = encoder.finish::<Root>();
        assert_eq!(
            data,
            [
                &header(0)[..],
                parse("0x0000000000000000000000000000000000000000000000000000000000001234")
                    .as_bytes(),
                parse("0x0000000000000000000000000000000000000000000000000000000000000000")
                    .as_bytes(),
                parse("0x7ffffffffffffffffffffffffffffffe0673ddf29e9b5547c000000000000000")
                    .as_bytes(),
            ]
            .concat()
        );
    }

    #[test]
    fn test_hashes() {
        let mut encoder = Encoder::default();
        encoder.push_hash(H256::repeat_byte(0xaa));
        encoder.push_hashes([H256::repeat_byte(0xbb), H256::repeat_byte(0xcc)]);
        let data = encoder.finish::<Root>();
        assert_eq!(
            data,
            [
                &header(3)[..],
                H256::repeat_byte(0xaa).as_bytes(),
                H256::repeat_byte(0xbb).as_bytes(),
                H256::repeat_byte(0xcc).as_bytes(),
                &[0, 1, 2][..],
            ]
            .concat()
        );
    }

    #[test]
    fn test_pool_order() {
        let mut encoder = Encoder::default();
        encoder.push_hashes([
            H256::repeat_byte(0xdd),
            H256::repeat_byte(0xbb),
            H256::repeat_byte(0xcc),
            H256::repeat_byte(0xaa),
            H256::repeat_byte(0xcc),
            H256::repeat_byte(0xbb),
            H256::repeat_byte(0xcc),
        ]);
        let data = encoder.finish::<Root>();
        // 0xcc has three references, 0xbb two, and 0xdd and 0xaa one each (0xaa is smaller).
        assert_eq!(
            data,
            [
                &header(4)[..],
                H256::repeat_byte(0xcc).as_bytes(),
                H256::repeat_byte(0xbb).as_bytes(),
                H256::repeat_byte(0xaa).as_bytes(),
                H256::repeat_byte(0xdd).as_bytes(),
                &[3, 1, 0, 2, 0, 1, 0][..],
            ]
            .concat()
        );
    }

    #[test]
    fn test_long_pool_reference() {
        let mut encoder = Encoder::default();
        let hashes: Vec<H256> = (1..=129u64).map(H256::from_low_u64_be).collect();
        encoder.push_hashes(hashes.iter().copied());
        let data = encoder.finish::<Root>();
        assert_eq!(data.len(), 64 + 129 * 32 + 128 + 2);
        assert_eq!(&data[48..52], &[0, 0, 0, 129]);
        assert_eq!(
            &data[(64 + 128 * 32)..(64 + 129 * 32)],
            hashes[128].as_bytes()
        );
        assert_eq!(&data[(64 + 129 * 32 + 127)..], &[0x7f, 0x80, 0x80]);
    }

    #[test]
    fn test_mixed_items() {
        let mut encoder = Encoder::default();
        encoder.push_usize(2);
        encoder.push_hash(H256::repeat_byte(0xaa));
        encoder.push_scalar(BS::from_const(5));
        encoder.push_hash(H256::repeat_byte(0xaa));
        let data = encoder.finish::<Root>();
        assert_eq!(
            data,
            [
                &header(1)[..],
                H256::repeat_byte(0xaa).as_bytes(),
                &[2, 0][..],
                parse("0x0000000000000000000000000000000000000000000000000000000000000005")
                    .as_bytes(),
                &[0][..],
            ]
            .concat()
        );
    }
}
