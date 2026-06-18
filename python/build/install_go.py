import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

GO_VERSION = "1.24.4"
INSTALL_ROOT = Path("/usr/local")


def main() -> None:
    if shutil.which("go"):
        return

    machine = platform.machine().lower()
    arch = {
        "aarch64": "arm64",
        "arm64": "arm64",
        "x86_64": "amd64",
        "amd64": "amd64",
    }.get(machine)
    if arch is None:
        raise RuntimeError(f"unsupported Linux architecture for Go install: {machine}")

    archive_name = f"go{GO_VERSION}.linux-{arch}.tar.gz"
    url = f"https://go.dev/dl/{archive_name}"

    with tempfile.TemporaryDirectory() as temporary_directory:
        archive_path = Path(temporary_directory, archive_name)
        urllib.request.urlretrieve(url, archive_path)

        go_root = INSTALL_ROOT / "go"
        if go_root.exists():
            shutil.rmtree(go_root)

        with tarfile.open(archive_path) as archive:
            archive.extractall(INSTALL_ROOT)

    go_binary = INSTALL_ROOT / "go" / "bin" / "go"
    subprocess.run([str(go_binary), "version"], check=True)


if __name__ == "__main__":
    main()
