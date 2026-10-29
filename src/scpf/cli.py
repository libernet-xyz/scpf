"""The `scpf` command line interface."""

import argparse
import pathlib
import sys
from collections.abc import Sequence

import scpf
from scpf.descriptors import build_descriptor_pool, read_descriptor_set


def _make_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    prog="scpf",
    description="Compiles schemas of the Starkom Compact Proof Format (SCPF). If neither "
    "--encoder nor --decoder is given, the schema is only validated.",
  )
  parser.add_argument("--version", action="version", version=f"%(prog)s {scpf.__version__}")
  parser.add_argument(
    "--proto",
    type=pathlib.Path,
    required=True,
    metavar="PATH_TO_SERIALIZED_DESCRIPTORS",
    help="serialized FileDescriptorSet with the protobuf messages that the schema is linked to, "
    "including their imports (protoc --descriptor_set_out=PATH --include_imports)",
  )
  parser.add_argument(
    "--encoder",
    type=pathlib.Path,
    metavar="RUST_ENCODER_DESTINATION",
    help="where to write the generated Rust encoder",
  )
  parser.add_argument(
    "--decoder",
    type=pathlib.Path,
    metavar="RUST_DECODER_DESTINATION",
    help="where to write the generated Rust decoder",
  )
  parser.add_argument(
    "schema",
    type=pathlib.Path,
    metavar="PATH_TO_SCPF_SCHEMA",
    help="path of the SCPF schema to compile",
  )
  return parser


def main(arguments: Sequence[str] | None = None) -> int:
  """Runs the `scpf` command and returns its exit status.

  `arguments` defaults to the command line arguments of the process.
  """
  options = _make_parser().parse_args(arguments)
  try:
    pool = build_descriptor_pool(read_descriptor_set(options.proto))
    schema = options.schema.read_text(encoding="utf-8")
    compiler = scpf.Compiler(schema, pool)
    compiler.validate()
    encoder = compiler.generate_encoder() if options.encoder is not None else None
    decoder = compiler.generate_decoder() if options.decoder is not None else None
    if encoder is not None:
      options.encoder.write_text(encoder, encoding="utf-8")
    if decoder is not None:
      options.decoder.write_text(decoder, encoding="utf-8")
  except (OSError, SyntaxError, ValueError) as error:
    print(f"scpf: {error}", file=sys.stderr)
    return 1
  return 0
