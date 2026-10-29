import pytest

from scpf import compile_schema


def test_empty_schema() -> None:
  encoder, decoder = compile_schema("")
  assert encoder == ""
  assert decoder == ""


def test_schema() -> None:
  encoder, decoder = compile_schema("x = 42\n")
  assert encoder == ""
  assert decoder == ""


def test_syntax_error() -> None:
  with pytest.raises(SyntaxError):
    compile_schema("x = \n")
