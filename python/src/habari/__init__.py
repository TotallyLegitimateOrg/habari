import atexit
import ctypes
import json
import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from importlib.resources import as_file, files
from pathlib import Path

__version__ = "0.1.13"

_NATIVE_LIBRARY_ENV = "HABARI_NATIVE_LIBRARY"
_NATIVE_LIBRARY_NAMES = {
    "darwin": "libhabari.dylib",
    "linux": "libhabari.so",
    "win32": "habari.dll",
}
_LIST_FIELDS = frozenset(
    {
        "season_number",
        "part_number",
        "anime_type",
        "audio_term",
        "device_compatibility",
        "episode_number",
        "other_episode_number",
        "episode_number_alt",
        "language",
        "release_information",
        "release_version",
        "source",
        "subtitles",
        "video_term",
        "volume_number",
    }
)


@dataclass(slots=True, kw_only=True)
class Metadata:
    season_number: list[str] = field(default_factory=list)
    part_number: list[str] = field(default_factory=list)
    title: str = ""
    formatted_title: str = ""
    anime_type: list[str] = field(default_factory=list)
    year: str = ""
    audio_term: list[str] = field(default_factory=list)
    device_compatibility: list[str] = field(default_factory=list)
    episode_number: list[str] = field(default_factory=list)
    other_episode_number: list[str] = field(default_factory=list)
    episode_number_alt: list[str] = field(default_factory=list)
    episode_title: str = ""
    file_checksum: str = ""
    file_extension: str = ""
    file_name: str = ""
    language: list[str] = field(default_factory=list)
    release_group: str = ""
    release_information: list[str] = field(default_factory=list)
    release_version: list[str] = field(default_factory=list)
    source: list[str] = field(default_factory=list)
    subtitles: list[str] = field(default_factory=list)
    video_resolution: str = ""
    video_term: list[str] = field(default_factory=list)
    volume_number: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Metadata:
        values: dict[str, object] = {}
        for metadata_field in fields(cls):
            key = metadata_field.name
            value = data.get(key)
            if key in _LIST_FIELDS:
                values[key] = list(value) if value is not None else []
            else:
                values[key] = str(value) if value is not None else ""
        return cls(**values)

    def to_dict(self, omit_empty: bool = True) -> dict[str, object]:
        data = asdict(self)
        if not omit_empty:
            return data
        return {key: value for key, value in data.items() if value not in ("", [])}


_resource_context = None


def _native_library_name() -> str:
    try:
        return _NATIVE_LIBRARY_NAMES[sys.platform]
    except KeyError as exc:
        msg = f"habari-python does not provide a native library for {sys.platform!r}"
        raise ImportError(msg) from exc


def _native_library_path() -> str:
    override = os.environ.get(_NATIVE_LIBRARY_ENV)
    if override:
        path = Path(override)
        if not path.is_file():
            msg = f"{_NATIVE_LIBRARY_ENV} points to a missing file: {path}"
            raise ImportError(msg)
        return str(path)

    global _resource_context
    resource = files(__name__).joinpath("_native", _native_library_name())
    if not resource.is_file():
        msg = (
            "habari-python was installed without its native parser library. "
            "Reinstall from a wheel for your platform, or build from source with Go and CGO available."
        )
        raise ImportError(msg)

    _resource_context = as_file(resource)
    path = _resource_context.__enter__()
    atexit.register(_resource_context.__exit__, None, None, None)
    return str(path)


def _load_native_library() -> ctypes.CDLL:
    library = ctypes.CDLL(_native_library_path())
    library.HabariParseJSON.argtypes = [ctypes.c_char_p]
    library.HabariParseJSON.restype = ctypes.c_void_p
    library.HabariFree.argtypes = [ctypes.c_void_p]
    library.HabariFree.restype = None
    return library


_native = _load_native_library()


def parse(filename: str) -> Metadata:
    if not isinstance(filename, str):
        msg = f"filename must be str, got {type(filename).__name__}"
        raise TypeError(msg)
    if "\x00" in filename:
        raise ValueError("filename must not contain null bytes")

    pointer = _native.HabariParseJSON(filename.encode("utf-8"))
    if not pointer:
        raise RuntimeError("native parser returned a null pointer")

    try:
        payload = ctypes.string_at(pointer).decode("utf-8")
    finally:
        _native.HabariFree(pointer)

    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("native parser returned invalid metadata")
    return Metadata.from_dict(data)


__all__ = ["Metadata", "__version__", "parse"]
