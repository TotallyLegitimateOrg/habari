import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "python" / "src"
FIXTURE_PATH = PROJECT_ROOT / "test" / "data.json"
NATIVE_LIBRARY_NAMES = {
    "darwin": "libhabari.dylib",
    "linux": "libhabari.so",
    "win32": "habari.dll",
}
LIST_FIELDS = {
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
METADATA_FIELDS = LIST_FIELDS | {
    "title",
    "formatted_title",
    "year",
    "episode_title",
    "file_checksum",
    "file_extension",
    "file_name",
    "release_group",
    "video_resolution",
}


@pytest.fixture(scope="session")
def habari_module(tmp_path_factory: pytest.TempPathFactory):
    if os.environ.get("HABARI_TEST_INSTALLED_WHEEL") != "1":
        target_dir = tmp_path_factory.mktemp("habari-native")
        target = target_dir / NATIVE_LIBRARY_NAMES[sys.platform]
        env = os.environ.copy()
        env.setdefault("CGO_ENABLED", "1")
        subprocess.run(
            ["go", "build", "-buildmode=c-shared", "-o", str(target), "./python/bridge"],
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
        )
        os.environ["HABARI_NATIVE_LIBRARY"] = str(target)
        sys.path.insert(0, str(SRC_ROOT))

    import habari

    return habari


@pytest.fixture(scope="session")
def fixture_data():
    with FIXTURE_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def assert_metadata_matches(actual: dict[str, object], expected: dict[str, object]) -> None:
    unknown_fields = set(expected) - METADATA_FIELDS
    assert not unknown_fields

    expected = {
        key: value
        for key, value in expected.items()
        if value not in ("", [], None)
    }
    assert set(actual) == set(expected)
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if key in LIST_FIELDS:
            assert actual_value == expected_value, key
        else:
            assert actual_value == expected_value, key


def test_parse_returns_typed_metadata(habari_module) -> None:
    metadata = habari_module.parse("Hyouka (2012) S1-2 [BD 1080p HEVC OPUS] [Dual-Audio]")

    assert isinstance(metadata, habari_module.Metadata)
    assert metadata.title == "Hyouka"
    assert metadata.formatted_title == "Hyouka (2012)"
    assert metadata.year == "2012"
    assert metadata.season_number == ["1", "2"]
    assert metadata.video_resolution == "1080p"
    assert metadata.to_dict()["title"] == "Hyouka"
    assert "episode_title" not in metadata.to_dict()
    assert "episode_title" in metadata.to_dict(omit_empty=False)


def test_fixture_data_matches_go_expectations(
    habari_module,
    fixture_data,
) -> None:
    for expected in fixture_data:
        actual = habari_module.parse(expected["file_name"]).to_dict()
        assert_metadata_matches(actual, expected)


def test_python_output_matches_go_cli_json(habari_module) -> None:
    filename = "Jujutsu Kaisen S03E02 One More Time 1080p NF WEB-DL AAC2.0 H 264-VARYG (Jujutsu Kaisen: Shimetsu Kaiyuu - Zenpen, Multi-Subs)"
    completed = subprocess.run(
        ["go", "run", "./cmd/habari", "--json", filename],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert habari_module.parse(filename).to_dict() == json.loads(completed.stdout)


def test_version_is_aligned_with_latest_go_tag(habari_module) -> None:
    assert habari_module.__version__ == "0.1.14"


def test_parse_rejects_invalid_filename_type(habari_module) -> None:
    with pytest.raises(TypeError):
        habari_module.parse(123)
