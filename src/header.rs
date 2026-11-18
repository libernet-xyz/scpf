use primitive_types::H256;
use sha3::Digest;

/// The signature at the start of the header: the ASCII characters `SCPF`.
pub(crate) const SIGNATURE: &[u8; 4] = b"SCPF";

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
pub(crate) const HEADER_SIZE: usize = 64;

/// Returns the layout identifier of SCPF data whose root message is a protobuf message of type `M`:
/// the Keccak-256 hash of the [full name of the message](`prost::Name::full_name`), e.g.
/// `starkom.proto.plonk.v11.Proof`.
///
/// This is the hash of Ethereum's `KECCAK256` instruction rather than SHA3-256 (FIPS 202).
pub fn layout_identifier<M: prost::Name>() -> H256 {
    let mut hasher = sha3::Keccak256::new();
    hasher.update(M::full_name().as_bytes());
    H256::from_slice(hasher.finalize().as_slice())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(s: &'static str) -> H256 {
        s.parse().unwrap()
    }

    #[test]
    fn test_layout_identifier() {
        assert_eq!(
            layout_identifier::<prost_types::Timestamp>(),
            parse("0x88ac5a42c1e617f23ca0cd6eecb964171d4c8a8a41a4218a632e990b55fd6915")
        );
    }

    #[test]
    fn test_layout_identifier_of_another_message() {
        assert_eq!(
            layout_identifier::<prost_types::Duration>(),
            parse("0x1fa07945c8fe200d54562b9c80bbdfefaaf6e79fe3b95531b7dd38c4a8709ce4")
        );
    }
}
