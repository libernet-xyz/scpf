"""The `scpf` command line interface."""

import argparse
from collections.abc import Sequence

import scpf


def _make_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    prog="scpf",
    description="Compiles schemas of the Starkom Compact Proof Format (SCPF).",
  )
  parser.add_argument("--version", action="version", version=f"%(prog)s {scpf.__version__}")
  return parser


def main(arguments: Sequence[str] | None = None) -> int:
  """Runs the `scpf` command and returns its exit status.

  `arguments` defaults to the command line arguments of the process.
  """
  parser = _make_parser()
  parser.parse_args(arguments)
  parser.print_help()
  return 0
