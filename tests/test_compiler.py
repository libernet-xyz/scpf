from collections.abc import Callable

import pytest
from google.protobuf import descriptor_pool

from scpf import Compiler

Generator = Callable[[Compiler], str]

GENERATORS = [Compiler.generate_encoder, Compiler.generate_decoder]


def test_syntax_error(pool: descriptor_pool.DescriptorPool) -> None:
  with pytest.raises(SyntaxError):
    Compiler("x = \n", pool)


@pytest.mark.parametrize("schema", ["", "x = 42\n"])
def test_validate(pool: descriptor_pool.DescriptorPool, schema: str) -> None:
  compiler = Compiler(schema, pool)

  compiler.validate()
  compiler.validate()


@pytest.mark.parametrize("generate", GENERATORS)
def test_empty_schema(generate: Generator, pool: descriptor_pool.DescriptorPool) -> None:
  assert generate(Compiler("", pool)) == ""


@pytest.mark.parametrize("generate", GENERATORS)
def test_schema(generate: Generator, pool: descriptor_pool.DescriptorPool) -> None:
  assert generate(Compiler("x = 42\n", pool)) == ""
