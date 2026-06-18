import os
import platform
import subprocess
from pathlib import Path

from setuptools import Distribution, setup
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py

PROJECT_ROOT = Path(__file__).parent.resolve()
NATIVE_LIBRARY_NAMES = {
    "Darwin": "libhabari.dylib",
    "Linux": "libhabari.so",
    "Windows": "habari.dll",
}


def append_env_flag(env: dict[str, str], key: str, value: str) -> None:
    env[key] = f"{env[key]} {value}" if env.get(key) else value


class BuildPy(build_py):
    def run(self) -> None:
        super().run()
        self._build_native_library()

    def _build_native_library(self) -> None:
        system = platform.system()
        try:
            library_name = NATIVE_LIBRARY_NAMES[system]
        except KeyError as exc:
            msg = f"unsupported platform for habari-python native library: {system}"
            raise RuntimeError(msg) from exc

        target_dir = Path(self.build_lib, "habari", "_native")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / library_name

        env = os.environ.copy()
        env.setdefault("CGO_ENABLED", "1")
        if system == "Darwin":
            env.setdefault("MACOSX_DEPLOYMENT_TARGET", "11.0")
            append_env_flag(env, "CGO_CFLAGS", "-mmacosx-version-min=11.0")
            append_env_flag(env, "CGO_LDFLAGS", "-mmacosx-version-min=11.0")
        subprocess.run(
            ["go", "build", "-buildmode=c-shared", "-o", str(target), "./python/bridge"],
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
        )

        for generated_path in (target.with_suffix(".h"), target.with_suffix(".lib")):
            generated_path.unlink(missing_ok=True)


class BdistWheel(bdist_wheel):
    def finalize_options(self) -> None:
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self) -> tuple[str, str, str]:
        _python, _abi, platform_tag = super().get_tag()
        return "py3", "none", platform_tag


class BinaryDistribution(Distribution):
    def has_ext_modules(self) -> bool:
        return True


setup(
    cmdclass={
        "build_py": BuildPy,
        "bdist_wheel": BdistWheel,
    },
    distclass=BinaryDistribution,
)
