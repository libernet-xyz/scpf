import pathlib
import shutil
import subprocess
import sys
import sysconfig

import pytest

import scpf
from scpf.cli import main


def test_no_arguments() -> None:
  with pytest.raises(SystemExit) as exit_info:
    main([])
  assert exit_info.value.code == 2


def test_compile(tmp_path: pathlib.Path) -> None:
  schema = tmp_path / "proof.scpf"
  schema.write_text("x = 42\n")
  encoder_output = tmp_path / "encoder.rs"
  decoder_output = tmp_path / "decoder.rs"

  status = main(
    [
      str(schema),
      "--encoder-output",
      str(encoder_output),
      "--decoder-output",
      str(decoder_output),
    ]
  )

  assert status == 0
  assert encoder_output.read_text() == ""
  assert decoder_output.read_text() == ""


def test_missing_schema(tmp_path: pathlib.Path) -> None:
  encoder_output = tmp_path / "encoder.rs"
  decoder_output = tmp_path / "decoder.rs"

  status = main(
    [
      str(tmp_path / "missing.scpf"),
      "--encoder-output",
      str(encoder_output),
      "--decoder-output",
      str(decoder_output),
    ]
  )

  assert status == 1
  assert not encoder_output.exists()
  assert not decoder_output.exists()


def test_invalid_schema(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
  schema = tmp_path / "proof.scpf"
  schema.write_text("x = \n")
  encoder_output = tmp_path / "encoder.rs"
  decoder_output = tmp_path / "decoder.rs"

  status = main(
    [
      str(schema),
      "--encoder-output",
      str(encoder_output),
      "--decoder-output",
      str(decoder_output),
    ]
  )

  assert status == 1
  assert capsys.readouterr().err.startswith("scpf: ")
  assert not encoder_output.exists()
  assert not decoder_output.exists()


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
