"""The `scpf` command line interface."""

import argparse
import pathlib
import sys
from collections.abc import Sequence

import scpf


def _make_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    prog="scpf",
    description="Compiles schemas of the Starkom Compact Proof Format (SCPF).",
  )
  parser.add_argument("--version", action="version", version=f"%(prog)s {scpf.__version__}")
  parser.add_argument("schema", type=pathlib.Path, help="path of the SCPF schema to compile")
  parser.add_argument(
    "--encoder-output",
    type=pathlib.Path,
    required=True,
    metavar="PATH",
    help="where to write the generated Rust encoder",
  )
  parser.add_argument(
    "--decoder-output",
    type=pathlib.Path,
    required=True,
    metavar="PATH",
    help="where to write the generated Rust decoder",
  )
  return parser


def main(arguments: Sequence[str] | None = None) -> int:
  """Runs the `scpf` command and returns its exit status.

  `arguments` defaults to the command line arguments of the process.
  """
  options = _make_parser().parse_args(arguments)
  try:
    schema = options.schema.read_text(encoding="utf-8")
    encoder, decoder = scpf.compile_schema(schema)
    options.encoder_output.write_text(encoder, encoding="utf-8")
    options.decoder_output.write_text(decoder, encoding="utf-8")
  except (OSError, SyntaxError) as error:
    print(f"scpf: {error}", file=sys.stderr)
    return 1
  return 0
