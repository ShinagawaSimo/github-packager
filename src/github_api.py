import base64
import os
import re
import time

from typing import Iterable, Optional

from bs4 import BeautifulSoup
from fastcore.net import HTTP403ForbiddenError, HTTP404NotFoundError
from fastcore.xtras import obj2dict
from ghapi.core import GhApi
import requests

from config import LANGUAGE_GROUPS, PR_KEYWORDS


def normalize_repo(repo_url: str) -> str:
    """Normalize repository input into owner/name form.

    Args:
        repo_url: Repository URL, SSH URL, or owner/name slug.

    Returns:
        Normalized owner/name string.
    """
    if repo_url.startswith("http://") or repo_url.startswith("https://"):
        repo_path = re.sub(r"\.git$", "", repo_url).split("github.com/")[-1]
        return repo_path.strip("/")
    if repo_url.startswith("git@"):
        repo_path = repo_url.split(":")[-1]
        return re.sub(r"\.git$", "", repo_path).strip("/")
    return repo_url.strip("/")


class Repo:
    """GitHub repository wrapper providing convenience API helpers."""

    def __init__(self, owner: str, name: str, token: Optional[str] = None):
        """Initialize the repository client.

        Args:
            owner: Repository owner.
            name: Repository name.
            token: Optional GitHub token for authenticated requests.
        """
        self.owner = owner
        self.name = name
        self.token = token
        self.api = GhApi(token=token)
        print(f"GitHub: init repo {owner}/{name}")
        self.repo = self.call_api(self.api.repos.get, owner=owner, repo=name)

    def call_api(self, func, **kwargs):
        """Call a GitHub API function with retry on rate limits.

        Args:
            func: Callable GitHub API endpoint.
            **kwargs: Parameters forwarded to the endpoint.

        Returns:
            API response object or None when not found.
        """
        print(f"GitHub: call api {getattr(func, '__name__', str(func))}")
        while True:
            try:
                return func(**kwargs)
            except HTTP403ForbiddenError:
                while True:
                    rl = self.api.rate_limit.get()
                    if rl.resources.core.remaining > 0:
                        break
                    time.sleep(60 * 5)
            except HTTP404NotFoundError:
                return None

    def get_all_loop(self, func, per_page: int = 100, num_pages: Optional[int] = None, **kwargs):
        """Iterate over a paginated GitHub API list endpoint.

        Args:
            func: Callable GitHub API endpoint.
            per_page: Items per page.
            num_pages: Optional max pages to fetch.
            **kwargs: Parameters forwarded to the endpoint.

        Yields:
            Items returned by the paginated endpoint.
        """
        page = 1
        print(f"GitHub: paginate {getattr(func, '__name__', str(func))} per_page={per_page}")
        args = {
            "owner": self.owner,
            "repo": self.name,
            "per_page": per_page,
            **kwargs,
        }
        while True:
            print(f"GitHub: fetch page {page}")
            values = self.call_api(func, page=page, **args)
            if values is None:
                break
            for value in values:
                yield value
            if len(values) == 0:
                break
            if num_pages is not None and page >= num_pages:
                break
            page += 1

    def get_all_pulls(self, per_page: int = 100, num_pages: Optional[int] = None, state: str = "closed"):
        """List pull requests with pagination.

        Args:
            per_page: Items per page.
            num_pages: Optional max pages to fetch.
            state: Pull request state filter.

        Returns:
            Iterator of pull requests.
        """
        print(f"GitHub: list pulls state={state}")
        return self.get_all_loop(
            self.api.pulls.list,
            per_page=per_page,
            num_pages=num_pages,
            state=state,
        )

    def extract_resolved_issues(self, pull) -> tuple[list[str], list[str]]:
        """Extract issue numbers referenced in a pull request and commit messages.

        Args:
            pull: Pull request object from the API.

        Returns:
            Tuple of (issue_numbers, commit_messages).
        """
        issues_pat = re.compile(r"(\w+)\s+\#(\d+)")
        plain_pat = re.compile(r"#(\d+)")
        comments_pat = re.compile(r"(?s)<!--.*?-->")
        text = pull.title if pull.title else ""
        text += "\n" + (pull.body if pull.body else "")
        print(f"GitHub: collect commits for PR {pull.number}")
        commits = list(self.get_all_loop(self.api.pulls.list_commits, pull_number=pull.number))
        commit_messages = [commit.commit.message for commit in commits]
        text += "\n" + "\n".join(commit_messages)
        text = comments_pat.sub("", text)
        references = issues_pat.findall(text)
        resolved_issues_set = set()
        for word, issue_num in references:
            if word.lower() in PR_KEYWORDS:
                resolved_issues_set.add(issue_num)
        if resolved_issues_set:
            print(f"GitHub: resolved issues {sorted(resolved_issues_set)}")
            return list(resolved_issues_set), commit_messages
        fallback_refs = list(dict.fromkeys(plain_pat.findall(text)))
        if fallback_refs:
            print(f"GitHub: fallback issues {fallback_refs}")
        return fallback_refs, commit_messages


def detect_language(repo: Repo) -> str:
    """Detect primary language group for a repository.

    Args:
        repo: Repository API wrapper.

    Returns:
        Language group key.
    """
    print("GitHub: detect language")
    langs = repo.call_api(repo.api.repos.list_languages, owner=repo.owner, repo=repo.name)
    if not langs:
        return "python"
    top_lang = max(langs.items(), key=lambda x: x[1])[0]
    for group, names in LANGUAGE_GROUPS.items():
        if top_lang in names:
            return group
    return "python"


def fetch_readme(repo: Repo) -> str:
    """Fetch and decode repository README contents.

    Args:
        repo: Repository API wrapper.

    Returns:
        README content as text.
    """
    print("GitHub: fetch README")
    readme = repo.call_api(repo.api.repos.get_readme, owner=repo.owner, repo=repo.name)
    if not readme:
        return ""
    content = readme.get("content", "")
    if readme.get("encoding") == "base64":
        return base64.b64decode(content).decode("utf-8", errors="ignore")
    return content


def extract_problem_statement_and_hints(pull: dict, repo: Repo) -> tuple[str, str]:
    """Collect issue titles, bodies, and comments as problem text and hints.

    Args:
        pull: Pull request dictionary with resolved issues.
        repo: Repository API wrapper.

    Returns:
        Tuple of (problem_statement, hints_text).
    """
    if repo.name == "django":
        return extract_problem_statement_and_hints_django(pull, repo)
    text = ""
    all_hint_texts = list()
    for issue_number in pull["resolved_issues"]:
        print(f"GitHub: fetch issue {issue_number}")
        issue = repo.call_api(
            repo.api.issues.get,
            owner=repo.owner,
            repo=repo.name,
            issue_number=issue_number,
        )
        if issue is None:
            continue
        title = issue.title if issue.title else ""
        body = issue.body if issue.body else ""
        text += f"{title}\n{body}\n"
        comments = repo.get_all_loop(repo.api.issues.list_comments, issue_number=issue_number)
        for comment in comments:
            if comment.body:
                all_hint_texts.append(comment.body)
    problem_text = text.strip()
    if not problem_text:
        title = pull.get("title") or ""
        body = pull.get("body") or ""
        problem_text = f"{title}\n{body}".strip()
    commit_messages = pull.get("commit_messages") or []
    hints_text = "\n".join(all_hint_texts).strip()
    if commit_messages:
        commit_text = "\n".join(commit_messages).strip()
        if hints_text:
            hints_text = f"{hints_text}\n{commit_text}"
        else:
            hints_text = commit_text
    if not problem_text and commit_messages:
        problem_text = "\n".join(commit_messages).strip()
    return problem_text, hints_text


def extract_problem_statement_and_hints_django(pull: dict, repo: Repo) -> tuple[str, str]:
    """Collect problem statements from the Django tracker for referenced issues.

    Args:
        pull: Pull request dictionary with resolved issues.
        repo: Repository API wrapper.

    Returns:
        Tuple of (problem_statement, hints_text).
    """
    text = ""
    all_hints_text = list()
    for issue_number in pull["resolved_issues"]:
        print(f"GitHub: fetch django ticket {issue_number}")
        url = f"https://code.djangoproject.com/ticket/{issue_number}"
        resp = requests.get(url)
        if resp.status_code != 200:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        issue_desc = soup.find("div", {"id": "ticket"})
        if issue_desc is None:
            continue
        title = issue_desc.find("h1", class_="searchable")
        body = issue_desc.find("div", class_="description")
        title_text = re.sub(r"\s+", " ", title.get_text()).strip() if title else ""
        body_text = re.sub(r"\s+", " ", body.get_text()).strip() if body else ""
        text += f"{title_text}\n{body_text}\n"
        all_hints_text.append(body_text)
    problem_text = text.strip()
    if not problem_text:
        title = pull.get("title") or ""
        body = pull.get("body") or ""
        problem_text = f"{title}\n{body}".strip()
    commit_messages = pull.get("commit_messages") or []
    hints_text = "\n".join(all_hints_text).strip()
    if commit_messages:
        commit_text = "\n".join(commit_messages).strip()
        if hints_text:
            hints_text = f"{hints_text}\n{commit_text}"
        else:
            hints_text = commit_text
    if not problem_text and commit_messages:
        problem_text = "\n".join(commit_messages).strip()
    return problem_text, hints_text


def iter_pulls(
    repo: Repo,
    max_pulls: Optional[int],
    max_issues: Optional[int],
    issue_numbers: Optional[set[str]],
) -> Iterable[dict]:
    """Yield pull requests that resolve issues and match optional filters.

    Args:
        repo: Repository API wrapper.
        max_pulls: Optional maximum number of pulls to yield.
        max_issues: Optional maximum number of unique issues to collect.
        issue_numbers: Optional set of issue numbers to include.

    Yields:
        Pull request dictionaries with resolved issues.
    """
    seen_issues = set()
    print("GitHub: iterate pulls")
    for i_pull, pull in enumerate(repo.get_all_pulls(state="closed")):
        resolved, commit_messages = repo.extract_resolved_issues(pull)
        if issue_numbers:
            if not resolved or not any(x in issue_numbers for x in resolved):
                continue
        if not resolved and not commit_messages:
            continue
        pull_dict = obj2dict(pull)
        pull_dict["resolved_issues"] = resolved
        pull_dict["commit_messages"] = commit_messages
        yield pull_dict
        if max_issues is not None and resolved:
            seen_issues.update(resolved)
            if len(seen_issues) >= max_issues:
                break
        if max_pulls is not None and i_pull >= max_pulls:
            break


def create_repo(repo_url: str) -> Repo:
    """Create a Repo instance from a repository URL or slug.

    Args:
        repo_url: Repository URL, SSH URL, or owner/name slug.

    Returns:
        Repo instance.
    """
    repo_name = normalize_repo(repo_url)
    print(f"GitHub: create repo client for {repo_name}")
    owner, name = repo_name.split("/")
    token = os.environ.get("GITHUB_TOKEN")
    return Repo(owner, name, token=token)
