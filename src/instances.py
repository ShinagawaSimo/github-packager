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
    max_issues: Optional[int],
    issue_numbers: Optional[set[str]],
) -> list[dict]:
    """Build instance dictionaries from resolved-issue pull requests.

    Args:
        repo: Repository API wrapper.
        readme_text: README contents to embed.
        language: Language group key.
        max_pulls: Optional maximum number of pulls to process.
        max_issues: Optional maximum number of issues to process.
        issue_numbers: Optional set of issue numbers to include.

    Returns:
        List of instance dictionaries.
    """
    instances = []
    print("Instances: start building")
    for pull in iter_pulls(repo, max_pulls, max_issues, issue_numbers):
        pull_number = pull.get("number")
        print(f"Instances: process pull {pull_number}")
        patch, test_patch = extract_patches(pull)
        print(f"Instances: patches (code={len(patch)}, test={len(test_patch)})")
        problem_statement, hints = extract_problem_statement_and_hints(pull, repo)
        print(f"Instances: problem length={len(problem_statement)} hints length={len(hints)}")
        if not patch or not problem_statement:
            print(f"Instances: skip pull {pull_number} (missing patch or problem)")
            continue
        instance_id = (repo.repo.full_name + "-" + str(pull["number"])).replace("/", "__")
        commit_messages = pull.get("commit_messages") or []
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
                "commit_messages": commit_messages,
                "created_at": pull["created_at"],
                "readme": readme_text,
                "language": language,
            }
        )
        print(f"Instances: added {instance_id}")
    print(f"Instances: done (count={len(instances)})")
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
