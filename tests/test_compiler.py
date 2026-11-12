import sys
from collections.abc import Callable

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, text_format

from scpf import Compiler, SchemaError
from scpf.descriptors import build_descriptor_pool

Generator = Callable[[Compiler], str]

GENERATORS = [Compiler.generate_encoder, Compiler.generate_decoder]

# The descriptors of the following file, which has a field of every kind that validation tells
# apart:
#
#   syntax = "proto3";
#   package example;
#
#   message Proof {
#     uint32 degree_bound = 1;
#     uint64 max_rounds = 2;
#     bytes nonce = 3;
#     string name = 4;
#     int64 offset = 5;
#     bool blinded = 6;
#     repeated uint64 sizes = 7;
#     oneof choice {
#       uint64 first = 8;
#       uint64 second = 9;
#     }
#     optional uint64 limit = 10;
#     message Point {
#       bytes z = 1;
#     }
#     Point point = 11;
#   }
#
#   message Query {
#     uint64 index = 1;
#   }
PROOF_DESCRIPTORS = """
file {
  name: "proof.proto"
  package: "example"
  syntax: "proto3"
  message_type {
    name: "Proof"
    field { name: "degree_bound" number: 1 label: LABEL_OPTIONAL type: TYPE_UINT32 }
    field { name: "max_rounds" number: 2 label: LABEL_OPTIONAL type: TYPE_UINT64 }
    field { name: "nonce" number: 3 label: LABEL_OPTIONAL type: TYPE_BYTES }
    field { name: "name" number: 4 label: LABEL_OPTIONAL type: TYPE_STRING }
    field { name: "offset" number: 5 label: LABEL_OPTIONAL type: TYPE_INT64 }
    field { name: "blinded" number: 6 label: LABEL_OPTIONAL type: TYPE_BOOL }
    field { name: "sizes" number: 7 label: LABEL_REPEATED type: TYPE_UINT64 }
    field { name: "first" number: 8 label: LABEL_OPTIONAL type: TYPE_UINT64 oneof_index: 0 }
    field { name: "second" number: 9 label: LABEL_OPTIONAL type: TYPE_UINT64 oneof_index: 0 }
    field {
      name: "limit" number: 10 label: LABEL_OPTIONAL type: TYPE_UINT64
      oneof_index: 1 proto3_optional: true
    }
    field {
      name: "point" number: 11 label: LABEL_OPTIONAL type: TYPE_MESSAGE
      type_name: ".example.Proof.Point"
    }
    nested_type {
      name: "Point"
      field { name: "z" number: 1 label: LABEL_OPTIONAL type: TYPE_BYTES }
    }
    oneof_decl { name: "choice" }
    oneof_decl { name: "_limit" }
  }
  message_type {
    name: "Query"
    field { name: "index" number: 1 label: LABEL_OPTIONAL type: TYPE_UINT64 }
  }
}
"""


@pytest.fixture
def proof_pool() -> descriptor_pool.DescriptorPool:
  """The descriptor pool of `PROOF_DESCRIPTORS`."""
  descriptor_set = text_format.Parse(PROOF_DESCRIPTORS, descriptor_pb2.FileDescriptorSet())
  return build_descriptor_pool(descriptor_set)


def schema(*lines: str) -> str:
  """Joins the given lines into a schema."""
  return "".join(f"{line}\n" for line in lines)


def proof_schema(*body: str) -> str:
  """A schema declaring the `example` package and a `Proof` class with the given body lines."""
  return schema('package = "example"', "class Proof:", *(f"  {line}" for line in body))


VALID_SCHEMAS = [
  pytest.param(schema(), id="empty"),
  pytest.param(schema('package = "example"'), id="package only"),
  pytest.param(proof_schema("degree_bound: varint"), id="uint32 field"),
  pytest.param(proof_schema("max_rounds: varint"), id="uint64 field"),
  pytest.param(proof_schema("nonce: varint"), id="bytes field"),
  pytest.param(proof_schema("nonce: varint", "degree_bound: varint"), id="fields in any order"),
  pytest.param(proof_schema("class Point:", "  z: varint"), id="nested class"),
  pytest.param(
    proof_schema("max_rounds: varint", "class Point:", "  z: varint"),
    id="fields and nested class",
  ),
  pytest.param(
    schema(
      'package = "example"',
      "class Proof:",
      "  degree_bound: varint",
      "class Query:",
      "  index: varint",
    ),
    id="two classes",
  ),
  pytest.param(
    schema("class Query:", "  index: varint", 'package = "example"'),
    id="package declared after the classes",
  ),
]

INVALID_SCHEMAS = [
  pytest.param(
    schema('package = "example"', "class Missing:", "  index: varint"),
    id="class without message",
  ),
  pytest.param(schema("class Proof:", "  degree_bound: varint"), id="missing package"),
  pytest.param(
    schema('package = "other"', "class Proof:", "  degree_bound: varint"), id="wrong package"
  ),
  pytest.param(
    schema('package = "example"', "class Point:", "  z: varint"),
    id="nested message as a top-level class",
  ),
  pytest.param(
    proof_schema("class Missing:", "  z: varint"), id="nested class without nested message"
  ),
  pytest.param(
    proof_schema("class Query:", "  index: varint"), id="top-level message as a nested class"
  ),
  pytest.param(proof_schema("missing: varint"), id="field without protobuf field"),
  pytest.param(proof_schema("index: varint"), id="field of another message"),
  pytest.param(proof_schema("degree_bound: Varint"), id="capitalized varint"),
  pytest.param(proof_schema("degree_bound: int"), id="unknown type"),
  pytest.param(proof_schema("degree_bound: array[varint, 2]"), id="array"),
  pytest.param(proof_schema('degree_bound: "varint"'), id="string annotation"),
  pytest.param(proof_schema("degree_bound: varint = 4"), id="field with value"),
  pytest.param(proof_schema("self.degree_bound: varint"), id="attribute as field name"),
  pytest.param(proof_schema("name: varint"), id="string protobuf field"),
  pytest.param(proof_schema("offset: varint"), id="signed protobuf field"),
  pytest.param(proof_schema("blinded: varint"), id="bool protobuf field"),
  pytest.param(proof_schema("point: varint"), id="message protobuf field"),
  pytest.param(proof_schema("sizes: varint"), id="repeated protobuf field"),
  pytest.param(proof_schema("first: varint"), id="oneof protobuf field"),
  pytest.param(proof_schema("limit: varint"), id="optional protobuf field"),
  pytest.param(proof_schema("degree_bound: varint", "degree_bound: varint"), id="duplicate field"),
  pytest.param(
    schema(
      'package = "example"', "class Query:", "  index: varint", "class Query:", "  index: varint"
    ),
    id="duplicate class",
  ),
  pytest.param(
    proof_schema("class Point:", "  z: varint", "class Point:", "  z: varint"),
    id="duplicate nested class",
  ),
  pytest.param(schema('package = "example"', 'package = "example"'), id="duplicate package"),
  pytest.param(schema("package = 42"), id="package that isn't a string"),
  pytest.param(schema("x = 42"), id="top-level assignment"),
  pytest.param(schema("def f():", "  pass"), id="top-level function"),
  pytest.param(schema("import os"), id="top-level import"),
  pytest.param(schema('"""Docstring."""'), id="top-level docstring"),
  pytest.param(proof_schema("pass"), id="pass in class"),
  pytest.param(proof_schema("degree_bound = 4"), id="assignment in class"),
  pytest.param(proof_schema("def f(self):", "    pass"), id="method"),
  pytest.param(proof_schema('"""Docstring."""'), id="docstring in class"),
  pytest.param(
    schema('package = "example"', "class Proof(Message):", "  degree_bound: varint"),
    id="base class",
  ),
  pytest.param(
    schema('package = "example"', "class Proof(metaclass=Meta):", "  degree_bound: varint"),
    id="class keyword",
  ),
  pytest.param(
    schema('package = "example"', "@dataclass", "class Proof:", "  degree_bound: varint"),
    id="class decorator",
  ),
  pytest.param(
    proof_schema("class Point(Message):", "  z: varint"), id="nested class with base class"
  ),
]


def test_syntax_error(proof_pool: descriptor_pool.DescriptorPool) -> None:
  with pytest.raises(SyntaxError):
    Compiler("x = \n", proof_pool)


@pytest.mark.parametrize("schema", VALID_SCHEMAS)
def test_valid_schema(proof_pool: descriptor_pool.DescriptorPool, schema: str) -> None:
  compiler = Compiler(schema, proof_pool)

  compiler.validate()


@pytest.mark.parametrize("schema", INVALID_SCHEMAS)
def test_invalid_schema(proof_pool: descriptor_pool.DescriptorPool, schema: str) -> None:
  compiler = Compiler(schema, proof_pool)

  with pytest.raises(SchemaError):
    compiler.validate()


@pytest.mark.skipif(sys.version_info < (3, 12), reason="type parameters need Python 3.12")
def test_type_parameters(proof_pool: descriptor_pool.DescriptorPool) -> None:
  compiler = Compiler(
    schema('package = "example"', "class Proof[T]:", "  degree_bound: varint"), proof_pool
  )

  with pytest.raises(SchemaError):
    compiler.validate()


def test_validate_twice(proof_pool: descriptor_pool.DescriptorPool) -> None:
  compiler = Compiler(proof_schema("degree_bound: varint"), proof_pool)

  compiler.validate()
  compiler.validate()


@pytest.mark.parametrize("generate", GENERATORS)
def test_generate(generate: Generator, proof_pool: descriptor_pool.DescriptorPool) -> None:
  compiler = Compiler(proof_schema("degree_bound: varint"), proof_pool)

  assert generate(compiler) == ""


@pytest.mark.parametrize("generate", GENERATORS)
def test_generate_from_invalid_schema(
  generate: Generator, proof_pool: descriptor_pool.DescriptorPool
) -> None:
  compiler = Compiler(proof_schema("missing: varint"), proof_pool)

  with pytest.raises(SchemaError):
    generate(compiler)
