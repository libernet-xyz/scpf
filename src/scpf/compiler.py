"""Generation of Rust code from SCPF schemas."""

import ast

from google.protobuf import descriptor, descriptor_pool

# The types of the protobuf fields that a `varint` field can be linked to. A `bytes` field holds an
# unsigned integer in little-endian byte order.
_VARINT_FIELD_TYPES = frozenset(
  {
    descriptor.FieldDescriptor.TYPE_UINT32,
    descriptor.FieldDescriptor.TYPE_UINT64,
    descriptor.FieldDescriptor.TYPE_BYTES,
  }
)


class SchemaError(ValueError):
  """An invalid SCPF schema, or one that doesn't match the protobuf messages it's linked to."""

  def __init__(self, node: ast.stmt, message: str):
    super().__init__(f"line {node.lineno}: {message}")


def _assigns_package(statement: ast.Assign) -> bool:
  """Returns true iff `statement` is an assignment to `package`, i.e. the package declaration."""
  return (
    len(statement.targets) == 1
    and isinstance(statement.targets[0], ast.Name)
    and statement.targets[0].id == "package"
  )


def _read_package(statement: ast.Assign) -> str:
  """Returns the protobuf package of a package declaration, which must be a string literal."""
  if not (isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str)):
    raise SchemaError(statement, "the package must be a string literal")
  return statement.value.value


def _check_unique_names(classes: list[ast.ClassDef]) -> None:
  """Checks that no two of the given sibling classes have the same name."""
  names: set[str] = set()
  for class_def in classes:
    if class_def.name in names:
      raise SchemaError(class_def, f"class `{class_def.name}` is defined more than once")
    names.add(class_def.name)


def _validate_field(statement: ast.AnnAssign, message: descriptor.Descriptor) -> str:
  """Validates a field against the protobuf message of its class, returning the field's name."""
  if not isinstance(statement.target, ast.Name):
    raise SchemaError(statement, "field names must be plain identifiers")
  name = statement.target.id
  if statement.value is not None:
    raise SchemaError(statement, f"field `{name}` must not have a value")
  if not (isinstance(statement.annotation, ast.Name) and statement.annotation.id == "varint"):
    raise SchemaError(statement, f"field `{name}` must be a `varint`")
  field = message.fields_by_name.get(name)
  if field is None:
    raise SchemaError(statement, f"protobuf message `{message.full_name}` has no field `{name}`")
  if field.type not in _VARINT_FIELD_TYPES:
    raise SchemaError(
      statement,
      f"protobuf field `{field.full_name}` must be a `uint32`, `uint64`, or `bytes` to be linked "
      "to a varint",
    )
  if field.is_repeated:
    raise SchemaError(
      statement,
      f"protobuf field `{field.full_name}` is repeated, so it can't be linked to a varint",
    )
  if field.has_presence:
    raise SchemaError(
      statement,
      f"protobuf field `{field.full_name}` tracks presence (it's `optional` or in a `oneof`), "
      "which a varint can't represent",
    )
  return name


def _validate_class(class_def: ast.ClassDef, message: descriptor.Descriptor) -> None:
  """Validates a class and its nested classes against the protobuf message it's linked to."""
  # `type_params` exists since Python 3.12.
  if (
    class_def.decorator_list
    or class_def.bases
    or class_def.keywords
    or getattr(class_def, "type_params", [])
  ):
    raise SchemaError(
      class_def,
      f"class `{class_def.name}` must not have decorators, base classes, keywords, or type "
      "parameters",
    )
  field_names: set[str] = set()
  nested_classes: list[ast.ClassDef] = []
  for statement in class_def.body:
    if isinstance(statement, ast.ClassDef):
      nested_classes.append(statement)
    elif isinstance(statement, ast.AnnAssign):
      name = _validate_field(statement, message)
      if name in field_names:
        raise SchemaError(statement, f"field `{name}` is declared more than once")
      field_names.add(name)
    else:
      raise SchemaError(
        statement, f"only fields and nested classes are allowed in class `{class_def.name}`"
      )
  _check_unique_names(nested_classes)
  for nested_class in nested_classes:
    nested_message = message.nested_types_by_name.get(nested_class.name)
    if nested_message is None:
      raise SchemaError(
        nested_class,
        f"protobuf message `{message.full_name}` has no nested message `{nested_class.name}`",
      )
    _validate_class(nested_class, nested_message)


def _validate_module(module: ast.Module, pool: descriptor_pool.DescriptorPool) -> None:
  """Validates a whole schema: an optional package declaration, and the classes."""
  package = ""
  package_declared = False
  classes: list[ast.ClassDef] = []
  for statement in module.body:
    if isinstance(statement, ast.ClassDef):
      classes.append(statement)
    elif isinstance(statement, ast.Assign) and _assigns_package(statement):
      if package_declared:
        raise SchemaError(statement, "the package is declared more than once")
      package = _read_package(statement)
      package_declared = True
    else:
      raise SchemaError(
        statement, "only classes and the package declaration are allowed at the top level"
      )
  _check_unique_names(classes)
  for class_def in classes:
    full_name = f"{package}.{class_def.name}" if package else class_def.name
    try:
      message = pool.FindMessageTypeByName(full_name)
    except KeyError:
      raise SchemaError(class_def, f"there's no protobuf message `{full_name}`") from None
    _validate_class(class_def, message)


class Compiler:
  """Compiler of an SCPF schema.

  A schema is written in a subset of Python's syntax, and it's only parsed, never executed. It
  consists of an optional package declaration, e.g. `package = "starkom.proto.pcs.v10"`, and of
  classes describing SCPF messages.

  Every class is linked to the protobuf message with the same name in the declared package (or in
  the root package if none is declared), and every nested class to the nested message with the same
  name. Every field of a class is linked to the field of its message with the same name, but the
  message may have more fields than the class.

  For now all fields are varints, declared as `name: varint`, and they can only be linked to
  singular `uint32`, `uint64`, and `bytes` protobuf fields without presence tracking. A `bytes`
  field holds an unsigned integer in little-endian byte order.
  """

  def __init__(self, schema: str, pool: descriptor_pool.DescriptorPool):
    """Parses an SCPF schema.

    `pool` holds the protobuf messages that the schema is linked to (see
    `scpf.descriptors.build_descriptor_pool`).

    Raises `SyntaxError` if the schema isn't syntactically valid.
    """
    self._tree = ast.parse(schema)
    self._pool = pool
    self._validated = False

  def validate(self) -> None:
    """Validates the schema, raising `SchemaError` if it's invalid.

    Validation is only performed once: later calls return immediately, and the code generators
    call this method themselves.
    """
    if self._validated:
      return

    _validate_module(self._tree, self._pool)

    self._validated = True

  def generate_encoder(self) -> str:
    """Generates the Rust code of the encoder, after validating the schema."""
    self.validate()

    # TODO

    return ""

  def generate_decoder(self) -> str:
    """Generates the Rust code of the decoder, after validating the schema."""
    self.validate()

    # TODO

    return ""
