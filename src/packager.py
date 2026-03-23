import argparse
import sys

from pathlib import Path
from typing import Optional

from config import BATCH_SINGLE_IMAGE_BASE, LANGUAGE_IMAGE_MAP
from github_api import create_repo, detect_language, fetch_readme, normalize_repo
from images import build_batch_image, build_instance_image
from instances import build_instances, write_instances


def main(
    repo_url: Optional[str] = None,
    batch: bool = False,
    output_dir: Optional[str] = None,
    max_pulls: Optional[int] = None,
    issue_numbers: Optional[list[str]] = None,
    language: Optional[str] = None,
    image_tag: Optional[str] = None,
    no_build: bool = False,
    single_image: bool = False,
):
    """Run the packager for a single repository or batch mode.

    Args:
        repo_url: Repository URL or owner/name slug for single mode.
        batch: Whether to use repositories.txt batch mode.
        output_dir: Output directory for instances and images.
        max_pulls: Optional maximum number of pulls to process.
        issue_numbers: Optional list of issue numbers to include.
        language: Optional override of detected language group.
        image_tag: Optional docker image tag prefix.
        no_build: Whether to skip Docker image building.
        single_image: Whether to build one batch image for all repos.
    """
    if output_dir is None or (repo_url is None and not batch):
        parser = build_parser()
        args = parser.parse_args()
        return main(**vars(args))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if batch:
        repo_list_path = get_repo_list_path()
        repo_urls, errors = load_repo_list(repo_list_path)
        if errors:
            for line in errors:
                print(f"Invalid repository entry: {line}", file=sys.stderr)
        all_instances = []
        for single_repo_url in repo_urls:
            instances = run_single_repo(
                repo_url=single_repo_url,
                output_dir=output_path / normalize_repo(single_repo_url).replace("/", "__"),
                max_pulls=max_pulls,
                issue_numbers=issue_numbers,
                language=language,
                image_tag=image_tag,
                no_build=no_build or single_image,
            )
            all_instances.extend(instances)
        if single_image and not no_build and all_instances:
            build_root = output_path / "images"
            build_root.mkdir(parents=True, exist_ok=True)
            tag = image_tag or "github_packager"
            build_batch_image(all_instances, BATCH_SINGLE_IMAGE_BASE, build_root, tag)
        return

    run_single_repo(
        repo_url=repo_url,
        output_dir=output_path,
        max_pulls=max_pulls,
        issue_numbers=issue_numbers,
        language=language,
        image_tag=image_tag,
        no_build=no_build,
    )


def get_repo_list_path() -> Path:
    """Resolve the repositories.txt path in the project root.

    Returns:
        Path to repositories.txt.
    """
    return Path(__file__).resolve().parents[1] / "repositories.txt"


def load_repo_list(repo_path: Path) -> tuple[list[str], list[str]]:
    """Load repository entries and collect invalid lines.

    Args:
        repo_path: Path to repositories.txt.

    Returns:
        Tuple of (valid_repos, invalid_lines).
    """
    if not repo_path.exists():
        raise FileNotFoundError(f"repositories.txt not found at {repo_path}")
    lines = repo_path.read_text(encoding="utf-8").splitlines()
    repos = []
    errors = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            normalized = normalize_repo(line)
            parts = normalized.split("/")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError("invalid")
        except Exception:
            errors.append(line)
            continue
        repos.append(line)
    return repos, errors


def run_single_repo(
    repo_url: str,
    output_dir: Path,
    max_pulls: Optional[int],
    issue_numbers: Optional[list[str]],
    language: Optional[str],
    image_tag: Optional[str],
    no_build: bool,
) -> list[dict]:
    """Process one repository and optionally build images.

    Args:
        repo_url: Repository URL or owner/name slug.
        output_dir: Output directory for instances and images.
        max_pulls: Optional maximum number of pulls to process.
        issue_numbers: Optional list of issue numbers to include.
        language: Optional override of detected language group.
        image_tag: Optional docker image tag prefix.
        no_build: Whether to skip Docker image building.

    Returns:
        Instance dictionaries for the repository.
    """
    repo_name = normalize_repo(repo_url)
    repo = create_repo(repo_url)
    readme_text = fetch_readme(repo)
    detected_language = language or detect_language(repo)
    issue_set = set(issue_numbers) if issue_numbers else None
    instances = build_instances(repo, readme_text, detected_language, max_pulls, issue_set)
    output_dir.mkdir(parents=True, exist_ok=True)
    instances_path = output_dir / f"{repo_name.replace('/', '__')}-instances.jsonl"
    write_instances(instances, instances_path)
    if no_build:
        return instances
    image_base = LANGUAGE_IMAGE_MAP.get(detected_language, LANGUAGE_IMAGE_MAP["python"])
    build_root = output_dir / "images"
    build_root.mkdir(parents=True, exist_ok=True)
    tag = image_tag or repo_name.replace("/", "__")
    for instance in instances:
        build_instance_image(instance, image_base, build_root, tag)
    return instances


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo_url", type=str, required=False)
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--max_pulls", type=int, default=None)
    parser.add_argument("--issue_numbers", nargs="*", default=None)
    parser.add_argument("--language", type=str, default=None)
    parser.add_argument("--image_tag", type=str, default=None)
    parser.add_argument("--no_build", action="store_true")
    parser.add_argument("--single_image", action="store_true")
    return parser


if __name__ == "__main__":
    main()
