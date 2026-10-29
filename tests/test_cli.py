import pathlib
import shutil
import subprocess
import sys
import sysconfig

import pytest

import scpf
from scpf.cli import main


@pytest.fixture
def schema_path(tmp_path: pathlib.Path) -> pathlib.Path:
  path = tmp_path / "proof.scpf"
  path.write_text("x = 42\n")
  return path


def test_no_arguments() -> None:
  with pytest.raises(SystemExit) as exit_info:
    main([])
  assert exit_info.value.code == 2


def test_missing_proto_argument(schema_path: pathlib.Path) -> None:
  with pytest.raises(SystemExit) as exit_info:
    main([str(schema_path)])
  assert exit_info.value.code == 2


def test_missing_schema_argument(descriptor_path: pathlib.Path) -> None:
  with pytest.raises(SystemExit) as exit_info:
    main(["--proto", str(descriptor_path)])
  assert exit_info.value.code == 2


def test_validate_only(
  tmp_path: pathlib.Path, descriptor_path: pathlib.Path, schema_path: pathlib.Path
) -> None:
  status = main(["--proto", str(descriptor_path), str(schema_path)])

  assert status == 0
  assert sorted(path.name for path in tmp_path.iterdir()) == ["example.desc", "proof.scpf"]


def test_encoder_and_decoder(
  tmp_path: pathlib.Path, descriptor_path: pathlib.Path, schema_path: pathlib.Path
) -> None:
  encoder = tmp_path / "encoder.rs"
  decoder = tmp_path / "decoder.rs"

  status = main(
    [
      "--proto",
      str(descriptor_path),
      "--encoder",
      str(encoder),
      "--decoder",
      str(decoder),
      str(schema_path),
    ]
  )

  assert status == 0
  assert encoder.read_text() == ""
  assert decoder.read_text() == ""


@pytest.mark.parametrize(
  ("flag", "written", "skipped"),
  [
    ("--encoder", "encoder.rs", "decoder.rs"),
    ("--decoder", "decoder.rs", "encoder.rs"),
  ],
)
def test_single_output(
  tmp_path: pathlib.Path,
  descriptor_path: pathlib.Path,
  schema_path: pathlib.Path,
  flag: str,
  written: str,
  skipped: str,
) -> None:
  status = main(["--proto", str(descriptor_path), flag, str(tmp_path / written), str(schema_path)])

  assert status == 0
  assert (tmp_path / written).exists()
  assert not (tmp_path / skipped).exists()


def test_missing_schema(tmp_path: pathlib.Path, descriptor_path: pathlib.Path) -> None:
  encoder = tmp_path / "encoder.rs"

  status = main(
    [
      "--proto",
      str(descriptor_path),
      "--encoder",
      str(encoder),
      str(tmp_path / "missing.scpf"),
    ]
  )

  assert status == 1
  assert not encoder.exists()


def test_invalid_schema(
  tmp_path: pathlib.Path, descriptor_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
  schema = tmp_path / "invalid.scpf"
  schema.write_text("x = \n")
  encoder = tmp_path / "encoder.rs"

  status = main(["--proto", str(descriptor_path), "--encoder", str(encoder), str(schema)])

  assert status == 1
  assert capsys.readouterr().err.startswith("scpf: ")
  assert not encoder.exists()


def test_missing_descriptors(tmp_path: pathlib.Path, schema_path: pathlib.Path) -> None:
  encoder = tmp_path / "encoder.rs"

  status = main(
    ["--proto", str(tmp_path / "missing.desc"), "--encoder", str(encoder), str(schema_path)]
  )

  assert status == 1
  assert not encoder.exists()


def test_invalid_descriptors(tmp_path: pathlib.Path, schema_path: pathlib.Path) -> None:
  descriptors = tmp_path / "invalid.desc"
  descriptors.write_bytes(b"\xff\xff\xff")
  encoder = tmp_path / "encoder.rs"

  status = main(["--proto", str(descriptors), "--encoder", str(encoder), str(schema_path)])

  assert status == 1
  assert not encoder.exists()


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
  with pytest.raises(SystemExit) as exit_info:
    main(["--version"])
  assert exit_info.value.code == 0
  assert capsys.readouterr().out == f"scpf {scpf.__version__}\n"


def test_unknown_argument() -> None:
  with pytest.raises(SystemExit) as exit_info:
    main(["--frobulate"])
  assert exit_info.value.code == 2


def test_run_as_module() -> None:
  result = subprocess.run(
    [sys.executable, "-m", "scpf", "--version"], capture_output=True, text=True, check=False
  )
  assert result.returncode == 0
  assert result.stdout == f"scpf {scpf.__version__}\n"


def test_run_installed_command() -> None:
  command = shutil.which("scpf", path=sysconfig.get_path("scripts"))
  assert command is not None
  result = subprocess.run([command, "--version"], capture_output=True, text=True, check=False)
  assert result.returncode == 0
  assert result.stdout == f"scpf {scpf.__version__}\n"
