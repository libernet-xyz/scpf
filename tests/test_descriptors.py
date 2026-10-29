import pathlib

import pytest
from google.protobuf import descriptor_pb2

from scpf.descriptors import build_descriptor_pool, parse_descriptor_set, read_descriptor_set


def test_parse_descriptor_set(descriptor_set: descriptor_pb2.FileDescriptorSet) -> None:
  parsed = parse_descriptor_set(descriptor_set.SerializeToString())

  assert parsed == descriptor_set


def test_parse_empty_descriptor_set() -> None:
  parsed = parse_descriptor_set(b"")

  assert len(parsed.file) == 0


def test_parse_invalid_descriptor_set() -> None:
  with pytest.raises(ValueError):
    parse_descriptor_set(b"\xff\xff\xff")


def test_read_descriptor_set(
  descriptor_path: pathlib.Path, descriptor_set: descriptor_pb2.FileDescriptorSet
) -> None:
  parsed = read_descriptor_set(descriptor_path)

  assert parsed == descriptor_set


def test_read_missing_descriptor_set(tmp_path: pathlib.Path) -> None:
  with pytest.raises(OSError):
    read_descriptor_set(tmp_path / "missing.desc")


def test_build_descriptor_pool(descriptor_set: descriptor_pb2.FileDescriptorSet) -> None:
  pool = build_descriptor_pool(descriptor_set)

  proof = pool.FindMessageTypeByName("example.Proof")

  assert [field.name for field in proof.fields] == ["roots"]
  roots_type = proof.fields_by_name["roots"].message_type
  assert roots_type is not None
  assert roots_type.full_name == "example.Hash"


def test_build_descriptor_pool_missing_import(
  descriptor_set: descriptor_pb2.FileDescriptorSet,
) -> None:
  del descriptor_set.file[0]

  with pytest.raises(ValueError):
    build_descriptor_pool(descriptor_set)


def test_build_descriptor_pool_duplicate_file_with_different_contents(
  descriptor_set: descriptor_pb2.FileDescriptorSet,
) -> None:
  duplicate = descriptor_set.file.add()
  duplicate.CopyFrom(descriptor_set.file[0])
  duplicate.message_type[0].name = "Other"

  with pytest.raises(ValueError):
    build_descriptor_pool(descriptor_set)
