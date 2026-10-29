"""Loading of protobuf descriptors."""

import pathlib

from google.protobuf import descriptor_pb2, descriptor_pool
from google.protobuf.message import DecodeError


def parse_descriptor_set(data: bytes) -> descriptor_pb2.FileDescriptorSet:
  """Parses a serialized `FileDescriptorSet`, as written by `protoc --descriptor_set_out`.

  Raises `ValueError` if `data` isn't a valid `FileDescriptorSet`.
  """
  descriptor_set = descriptor_pb2.FileDescriptorSet()
  try:
    descriptor_set.ParseFromString(data)
  except DecodeError as error:
    raise ValueError(f"invalid descriptor set: {error}") from error
  return descriptor_set


def read_descriptor_set(path: pathlib.Path) -> descriptor_pb2.FileDescriptorSet:
  """Reads a serialized `FileDescriptorSet` from a file.

  Raises `OSError` if the file can't be read and `ValueError` if it isn't a valid
  `FileDescriptorSet`.
  """
  return parse_descriptor_set(path.read_bytes())


def build_descriptor_pool(
  descriptor_set: descriptor_pb2.FileDescriptorSet,
) -> descriptor_pool.DescriptorPool:
  """Builds a descriptor pool from the files of a `FileDescriptorSet`.

  The pool resolves the type references between the files, and lets callers look up messages by
  their full name, for example `pool.FindMessageTypeByName("starkom.proto.pcs.v9.Proof")`. The set
  must contain every file that its files import (`protoc --include_imports`), listed after the
  files they import, which is the order `protoc` writes them in.

  Raises `ValueError` if the set is inconsistent: a missing import, an unresolved type reference,
  or a duplicate definition.
  """
  pool = descriptor_pool.DescriptorPool()
  for file in descriptor_set.file:
    try:
      pool.AddSerializedFile(file.SerializeToString())
    except (TypeError, KeyError) as error:
      raise ValueError(f"invalid descriptor set: file {file.name!r}: {error}") from error
  return pool
