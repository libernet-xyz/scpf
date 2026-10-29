"""Generation of Rust code from SCPF schemas."""

import ast

from google.protobuf import descriptor_pool


class Compiler:
  """Compiler of an SCPF schema."""

  def __init__(self, schema: str, pool: descriptor_pool.DescriptorPool):
    """Parses an SCPF schema.

    `pool` holds the protobuf messages that the schema is linked to (see
    `scpf.descriptors.build_descriptor_pool`).

    Raises `SyntaxError` if the schema isn't syntactically valid.
    """
    self._tree = ast.parse(schema)
    self._pool = pool
    self._validated = False

  def validate(self) -> None:
    """Validates the schema, raising an exception if it's invalid.

    Validation is only performed once: later calls return immediately, and the code generators
    call this method themselves.
    """
    if self._validated:
      return

    # TODO

    self._validated = True

  def generate_encoder(self) -> str:
    """Generates the Rust code of the encoder, after validating the schema."""
    self.validate()

    # TODO

    return ""

  def generate_decoder(self) -> str:
    """Generates the Rust code of the decoder, after validating the schema."""
    self.validate()

    # TODO

    return ""
