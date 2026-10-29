import pathlib

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool

from scpf.descriptors import build_descriptor_pool


@pytest.fixture
def descriptor_set() -> descriptor_pb2.FileDescriptorSet:
  """A descriptor set with two files, the second one importing the first."""
  descriptor_set = descriptor_pb2.FileDescriptorSet()

  common = descriptor_set.file.add()
  common.name = "common.proto"
  common.package = "example"
  common.syntax = "proto3"
  hash_message = common.message_type.add()
  hash_message.name = "Hash"
  field = hash_message.field.add()
  field.name = "bytes"
  field.number = 1
  field.type = descriptor_pb2.FieldDescriptorProto.TYPE_BYTES
  field.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL

  main = descriptor_set.file.add()
  main.name = "main.proto"
  main.package = "example"
  main.syntax = "proto3"
  main.dependency.append("common.proto")
  proof = main.message_type.add()
  proof.name = "Proof"
  field = proof.field.add()
  field.name = "roots"
  field.number = 1
  field.type = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
  field.type_name = ".example.Hash"
  field.label = descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED

  return descriptor_set


@pytest.fixture
def pool(descriptor_set: descriptor_pb2.FileDescriptorSet) -> descriptor_pool.DescriptorPool:
  """The descriptor pool of the `descriptor_set` fixture."""
  return build_descriptor_pool(descriptor_set)


@pytest.fixture
def descriptor_path(
  tmp_path: pathlib.Path, descriptor_set: descriptor_pb2.FileDescriptorSet
) -> pathlib.Path:
  """The path of a file holding the serialized `descriptor_set` fixture."""
  path = tmp_path / "example.desc"
  path.write_bytes(descriptor_set.SerializeToString())
  return path
