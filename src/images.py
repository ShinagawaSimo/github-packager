import json

from pathlib import Path

from config import (
    LANGUAGE_BUILD_COMMANDS,
    LANGUAGE_BUILD_PACKAGES,
    LANGUAGE_TEST_COMMANDS,
)
from docker_tools import build_image


def write_metadata(build_dir: Path, instance: dict) -> None:
    """Write per-instance metadata files into the build directory.

    Args:
        build_dir: Build context directory for the instance.
        instance: Instance metadata dictionary.
    """
    metadata_dir = build_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "README.md").write_text(instance["readme"], encoding="utf-8")
    (metadata_dir / "metadata.json").write_text(
        json.dumps(instance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (metadata_dir / "patch.diff").write_text(instance["patch"], encoding="utf-8")
    (metadata_dir / "test_patch.diff").write_text(instance["test_patch"], encoding="utf-8")
    write_test_spec(
        metadata_dir / "test_spec.json",
        instance["language"],
        "/testbed/repo",
    )
    (metadata_dir / "run_eval.sh").write_text(
        render_eval_script(
            repo_dir="/testbed/repo",
            bundle_dir="/bundle",
            language=instance["language"],
        ),
        encoding="utf-8",
    )


def build_packages_for_language(language: str) -> list[str]:
    """Return additional apt packages to enable builds for a language.

    Args:
        language: Language group key.

    Returns:
        List of apt package names.
    """
    return LANGUAGE_BUILD_PACKAGES.get(language, [])


def build_commands_for_language(language: str) -> list[str]:
    """Return build commands for a language executed during image build.

    Args:
        language: Language group key.

    Returns:
        List of shell commands.
    """
    return LANGUAGE_BUILD_COMMANDS.get(language, [])


def test_commands_for_language(language: str) -> list[str]:
    """Return test commands for a language executed during evaluation.

    Args:
        language: Language group key.

    Returns:
        List of shell commands.
    """
    return LANGUAGE_TEST_COMMANDS.get(language, [])


def write_test_spec(output_path: Path, language: str, repo_dir: str) -> None:
    """Write a JSON test specification with build and test commands.

    Args:
        output_path: Destination path for the JSON file.
        language: Language group key.
        repo_dir: Repository directory inside the container.
    """
    payload = {
        "repo_dir": repo_dir,
        "build_commands": build_commands_for_language(language),
        "test_commands": test_commands_for_language(language),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def render_eval_script(repo_dir: str, bundle_dir: str, language: str) -> str:
    """Render a shell script that applies patches and runs tests.

    Args:
        repo_dir: Repository directory inside the container.
        bundle_dir: Bundle directory containing metadata and patches.
        language: Language group key.

    Returns:
        Shell script contents.
    """
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'REPO_DIR="{repo_dir}"',
        f'BUNDLE_DIR="{bundle_dir}"',
        'cd "$REPO_DIR"',
        'if [ -s "$BUNDLE_DIR/patch.diff" ]; then git apply "$BUNDLE_DIR/patch.diff"; fi',
        'if [ -s "$BUNDLE_DIR/test_patch.diff" ]; then git apply "$BUNDLE_DIR/test_patch.diff"; fi',
    ]
    for command in build_commands_for_language(language):
        lines.append(command)
    for command in test_commands_for_language(language):
        lines.append(command)
    lines.append('echo "TESTS_DONE"')
    return "\n".join(lines) + "\n"


def build_instance_image(instance: dict, base_image: str, build_root: Path, tag: str) -> str:
    """Build a single-instance image with metadata and compile steps.

    Args:
        instance: Instance metadata dictionary.
        base_image: Base image name.
        build_root: Root build directory.
        tag: Image tag prefix.

    Returns:
        Built image name.
    """
    build_dir = build_root / instance["instance_id"]
    build_dir.mkdir(parents=True, exist_ok=True)
    write_metadata(build_dir, instance)
    packages = build_packages_for_language(instance["language"])
    package_line = ""
    if packages:
        package_line = f" {' '.join(packages)}"
    dockerfile_lines = [
        f"FROM {base_image}",
        f"RUN apt-get update && apt-get install -y git ca-certificates curl{package_line} && rm -rf /var/lib/apt/lists/*",
        "WORKDIR /testbed",
        f"RUN git clone https://github.com/{instance['repo']} /testbed/repo",
        "WORKDIR /testbed/repo",
        f"RUN git reset --hard {instance['base_commit']}",
        "RUN git remote remove origin",
    ]
    for command in build_commands_for_language(instance["language"]):
        dockerfile_lines.append(f"RUN {command}")
    dockerfile_lines.append("COPY metadata/ /bundle/")
    dockerfile_lines.append("RUN chmod +x /bundle/run_eval.sh")
    dockerfile = "\n".join(dockerfile_lines)
    image_name = f"{tag}:{instance['instance_id']}"
    build_image(
        image_name=image_name,
        dockerfile=dockerfile,
        build_dir=build_dir,
        platform="linux/amd64",
        nocache=False,
    )
    return image_name


def write_batch_metadata(build_dir: Path, instances: list[dict]) -> None:
    """Write batch metadata layout for multiple instances.

    Args:
        build_dir: Build context directory for the batch image.
        instances: List of instance metadata dictionaries.
    """
    metadata_dir = build_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    for instance in instances:
        instance_dir = metadata_dir / instance["instance_id"]
        instance_dir.mkdir(parents=True, exist_ok=True)
        (instance_dir / "README.md").write_text(instance["readme"], encoding="utf-8")
        (instance_dir / "metadata.json").write_text(
            json.dumps(instance, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (instance_dir / "patch.diff").write_text(instance["patch"], encoding="utf-8")
        (instance_dir / "test_patch.diff").write_text(instance["test_patch"], encoding="utf-8")
        write_test_spec(
            instance_dir / "test_spec.json",
            instance["language"],
            f"/testbed/{instance['instance_id']}",
        )
    (metadata_dir / "run_eval.sh").write_text(
        render_batch_eval_script(
            bundle_dir="/bundle",
        ),
        encoding="utf-8",
    )


def render_batch_eval_script(bundle_dir: str) -> str:
    """Render a batch evaluation script requiring an instance id.

    Args:
        bundle_dir: Bundle directory containing per-instance metadata.

    Returns:
        Shell script contents.
    """
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'if [ "${1:-}" = "" ]; then echo "usage: run_eval.sh <instance_id>" >&2; exit 2; fi',
        f'BUNDLE_DIR="{bundle_dir}"',
        'INSTANCE_ID="$1"',
        'REPO_DIR="/testbed/$INSTANCE_ID"',
        'SPEC="$BUNDLE_DIR/$INSTANCE_ID/test_spec.json"',
        'export SPEC',
        'cd "$REPO_DIR"',
        'if [ -s "$BUNDLE_DIR/$INSTANCE_ID/patch.diff" ]; then git apply "$BUNDLE_DIR/$INSTANCE_ID/patch.diff"; fi',
        'if [ -s "$BUNDLE_DIR/$INSTANCE_ID/test_patch.diff" ]; then git apply "$BUNDLE_DIR/$INSTANCE_ID/test_patch.diff"; fi',
        'if [ ! -f "$SPEC" ]; then echo "missing test_spec.json" >&2; exit 1; fi',
        'python3 - <<\'PY\'',
        "import json",
        "import os",
        "import subprocess",
        "spec_path = os.environ['SPEC']",
        "with open(spec_path, 'r', encoding='utf-8') as f:",
        "    spec = json.load(f)",
        "for cmd in spec.get('build_commands', []):",
        "    subprocess.run(cmd, shell=True, check=True)",
        "for cmd in spec.get('test_commands', []):",
        "    subprocess.run(cmd, shell=True, check=True)",
        "PY",
        'echo "TESTS_DONE"',
    ]
    return "\n".join(lines) + "\n"


def build_batch_image(
    instances: list[dict],
    base_image: str,
    build_root: Path,
    tag: str,
) -> str:
    """Build a single image that contains multiple repositories and metadata.

    Args:
        instances: List of instance metadata dictionaries.
        base_image: Base image name.
        build_root: Root build directory.
        tag: Image tag prefix.

    Returns:
        Built image name.
    """
    build_dir = build_root / "batch"
    build_dir.mkdir(parents=True, exist_ok=True)
    write_batch_metadata(build_dir, instances)
    batch_packages = build_packages_for_language("batch")
    package_line = ""
    if batch_packages:
        package_line = f" {' '.join(batch_packages)}"
    dockerfile_lines = [
        f"FROM {base_image}",
        f"RUN apt-get update && apt-get install -y git ca-certificates curl{package_line} && rm -rf /var/lib/apt/lists/*",
        "WORKDIR /testbed",
    ]
    for instance in instances:
        repo = instance["repo"]
        instance_dir = instance["instance_id"]
        base_commit = instance["base_commit"]
        dockerfile_lines.extend(
            [
                f"RUN git clone https://github.com/{repo} /testbed/{instance_dir}",
                f"WORKDIR /testbed/{instance_dir}",
                f"RUN git reset --hard {base_commit}",
                "RUN git remote remove origin",
            ]
        )
        for command in build_commands_for_language(instance["language"]):
            dockerfile_lines.append(f"RUN {command}")
    dockerfile_lines.append("COPY metadata/ /bundle/")
    dockerfile_lines.append("RUN chmod +x /bundle/run_eval.sh")
    dockerfile = "\n".join(dockerfile_lines)
    image_name = f"{tag}:batch"
    build_image(
        image_name=image_name,
        dockerfile=dockerfile,
        build_dir=build_dir,
        platform="linux/amd64",
        nocache=False,
    )
    return image_name
