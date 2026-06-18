import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PACKAGE_NAME = "habari-python"
REQUIRES_PYTHON = ">=3.14"
ASSET_SUFFIXES = (".whl", ".tar.gz", ".zip")
INDEX_PATH = "packages"


@dataclass(frozen=True)
class Distribution:
    filename: str
    url: str
    sha256: str | None = None


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def package_file_pattern(package_name: str) -> re.Pattern[str]:
    package_prefix = re.escape(normalize_name(package_name)).replace("\\-", "[-_]")
    return re.compile(rf"^{package_prefix}-.+({'|'.join(re.escape(s) for s in ASSET_SUFFIXES)})$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def distribution_from_local_file(path: Path, repository: str, release_tag: str) -> Distribution:
    filename = path.name
    return Distribution(
        filename=filename,
        url=f"https://github.com/{repository}/releases/download/{release_tag}/{filename}",
        sha256=sha256_file(path),
    )


def local_distributions(dist_dir: Path, repository: str, release_tag: str, package_name: str) -> list[Distribution]:
    pattern = package_file_pattern(package_name)
    distributions = []
    for path in sorted(dist_dir.iterdir()):
        if path.is_file() and pattern.match(path.name):
            distributions.append(distribution_from_local_file(path, repository, release_tag))
    return distributions


def github_api_json(url: str, token: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "habari-package-index-generator",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def sha256_from_asset(asset: dict[str, object]) -> str | None:
    digest = asset.get("digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest.removeprefix("sha256:")
    return None


def release_distributions(repository: str, token: str, package_name: str) -> list[Distribution]:
    pattern = package_file_pattern(package_name)
    distributions = []
    page = 1
    while True:
        releases = github_api_json(
            f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}",
            token,
        )
        if not releases:
            break
        for release in releases:
            if release.get("draft"):
                continue
            for asset in release.get("assets", []):
                filename = asset.get("name", "")
                url = asset.get("browser_download_url")
                if pattern.match(filename) and isinstance(url, str):
                    distributions.append(
                        Distribution(
                            filename=filename,
                            url=url,
                            sha256=sha256_from_asset(asset),
                        )
                    )
        page += 1
    return sorted({dist.filename: dist for dist in distributions}.values(), key=lambda dist: dist.filename)


def write_html(path: Path, title: str, body_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(body_lines)
    path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '  <meta charset="utf-8">',
                f"  <title>{html.escape(title)}</title>",
                "</head>",
                "<body>",
                body,
                "</body>",
                "</html>",
                "",
            ]
        ),
        encoding="utf-8",
    )


def distribution_anchor(distribution: Distribution, requires_python: str) -> str:
    fragment = f"#sha256={distribution.sha256}" if distribution.sha256 else ""
    href = html.escape(f"{distribution.url}{fragment}", quote=True)
    filename = html.escape(distribution.filename)
    requires = html.escape(requires_python, quote=True)
    return f'  <a href="{href}" data-requires-python="{requires}">{filename}</a><br>'


def write_site(output_dir: Path, distributions: list[Distribution], package_name: str, requires_python: str) -> None:
    normalized_name = normalize_name(package_name)
    index_dir = output_dir / INDEX_PATH
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    write_html(
        output_dir / "index.html",
        "Habari Package Index",
        [
            "  <h1>Habari Package Index</h1>",
            f'  <a href="{INDEX_PATH}/">packages</a>',
        ],
    )
    write_html(
        index_dir / "index.html",
        "Habari Python Packages",
        [
            "  <h1>Habari Python Packages</h1>",
            f'  <a href="{normalized_name}/">{normalized_name}</a>',
        ],
    )
    write_html(
        index_dir / normalized_name / "index.html",
        f"Links for {normalized_name}",
        [
            f"  <h1>Links for {normalized_name}</h1>",
            *[distribution_anchor(dist, requires_python) for dist in distributions],
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a GitHub Pages Python package index.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-name", default=PACKAGE_NAME)
    parser.add_argument("--requires-python", default=REQUIRES_PYTHON)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "TotallyLegitimateOrg/habari"))
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument("--release-tag", default=os.environ.get("GITHUB_REF_NAME"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dist_dir:
        if not args.release_tag:
            raise SystemExit("--release-tag is required when --dist-dir is used")
        distributions = local_distributions(args.dist_dir, args.repository, args.release_tag, args.package_name)
    else:
        if not args.github_token:
            raise SystemExit("GITHUB_TOKEN is required when reading GitHub releases")
        distributions = release_distributions(args.repository, args.github_token, args.package_name)

    if not distributions:
        raise SystemExit(f"no distributions found for {args.package_name}")

    write_site(args.output_dir, distributions, args.package_name, args.requires_python)
    print(f"Wrote {len(distributions)} distributions to {args.output_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
