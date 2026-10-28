import shutil
import subprocess
import sys
import sysconfig

import pytest

import scpf
from scpf.cli import main


def test_no_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    status = main([])
    assert status == 0
    assert capsys.readouterr().out.startswith("usage: scpf")


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
