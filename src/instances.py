import json

from pathlib import Path
from typing import Optional

from github_api import Repo, iter_pulls, extract_problem_statement_and_hints
from patches import extract_patches


def build_instances(
    repo: Repo,
    readme_text: str,
    language: str,
    max_pulls: Optional[int],
    issue_numbers: Optional[set[str]],
) -> list[dict]:
    """Build instance dictionaries from resolved-issue pull requests.

    Args:
        repo: Repository API wrapper.
        readme_text: README contents to embed.
        language: Language group key.
        max_pulls: Optional maximum number of pulls to process.
        issue_numbers: Optional set of issue numbers to include.

    Returns:
        List of instance dictionaries.
    """
    instances = []
    for pull in iter_pulls(repo, max_pulls, issue_numbers):
        patch, test_patch = extract_patches(pull)
        problem_statement, hints = extract_problem_statement_and_hints(pull, repo)
        if not patch or not problem_statement:
            continue
        instance_id = (repo.repo.full_name + "-" + str(pull["number"])).replace("/", "__")
        instances.append(
            {
                "repo": repo.repo.full_name,
                "pull_number": pull["number"],
                "instance_id": instance_id,
                "issue_numbers": pull["resolved_issues"],
                "base_commit": pull["base"]["sha"],
                "patch": patch,
                "test_patch": test_patch,
                "problem_statement": problem_statement,
                "hints_text": hints,
                "created_at": pull["created_at"],
                "readme": readme_text,
                "language": language,
            }
        )
    return instances


def write_instances(instances: list[dict], output_path: Path) -> None:
    """Write instance dictionaries to a JSONL file.

    Args:
        instances: Instance dictionaries to write.
        output_path: Destination JSONL path.
    """
    with output_path.open("w", encoding="utf-8") as f:
        for inst in instances:
            f.write(json.dumps(inst, ensure_ascii=False) + "\n")
