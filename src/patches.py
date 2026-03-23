import requests

from unidiff import PatchSet


def extract_patches(pull: dict) -> tuple[str, str]:
    """Split a PR diff into code and test patches.

    Args:
        pull: Pull request dictionary with a diff_url.

    Returns:
        Tuple of (code_patch, test_patch).
    """
    patch = requests.get(pull["diff_url"]).text
    patch_test = ""
    patch_fix = ""
    for hunk in PatchSet(patch):
        if any(test_word in hunk.path for test_word in ["test", "tests", "e2e", "testing"]):
            patch_test += str(hunk)
        else:
            patch_fix += str(hunk)
    return patch_fix, patch_test
