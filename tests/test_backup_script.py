import gzip
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path("scripts/backup.sh").resolve()
BASH = shutil.which("bash")
BASH_UNAVAILABLE = BASH is None or os.name == "nt"


def _install_stub(directory: Path, body: str) -> Path:
    directory.mkdir()
    path = directory / "pg_dump"
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return directory


def _run_backup(tmp_path: Path, bin_dir: Path):
    assert BASH is not None
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "BACKUP_DIR": str(tmp_path),
        "POSTGRES_PASSWORD": "secret",
        "BACKUP_RETENTION_DAYS": "30",
    }
    env.pop("BACKUP_SCHEDULE", None)
    return subprocess.run(  # noqa: S603
        [BASH, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(BASH_UNAVAILABLE, reason="a functional Unix bash is required")
def test_failed_dump_does_not_publish_backup(tmp_path: Path):
    bin_dir = _install_stub(tmp_path / "bin", "#!/bin/sh\nexit 2\n")
    result = _run_backup(tmp_path, bin_dir)
    assert result.returncode != 0
    assert list(tmp_path.glob("*.sql.gz")) == []


@pytest.mark.skipif(BASH_UNAVAILABLE, reason="a functional Unix bash is required")
def test_env_password_creates_valid_nonempty_gzip(tmp_path: Path):
    bin_dir = _install_stub(
        tmp_path / "bin",
        "#!/bin/sh\nprintf '%s\\n' 'CREATE TABLE ok();'\n",
    )
    result = _run_backup(tmp_path, bin_dir)
    assert result.returncode == 0, result.stderr
    backups = list(tmp_path.glob("agenda_agenda_atende_*.sql.gz"))
    assert len(backups) == 1
    assert gzip.decompress(backups[0].read_bytes()).startswith(b"CREATE TABLE")
