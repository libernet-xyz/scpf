"""Compilation of SCPF schemas into Rust code."""

import ast


def compile_schema(schema: str) -> tuple[str, str]:
  """Compiles an SCPF schema into the Rust code of its encoder and decoder.

  Returns the encoder and the decoder, in that order. Raises `SyntaxError` if the schema isn't
  syntactically valid.
  """
  ast.parse(schema)

  # TODO

  return "", ""
