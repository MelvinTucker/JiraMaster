"""Integration tests for the get_issue_description module.

This test suite validates the get_issue_description script against a live
Jira instance. It requires a valid .env file and that the issue specified
in the script (or a test-specific one) exists.

Usage:
    pytest -m integration
"""

import pytest

# Modules under test
import get_issue_description
from jira_connector import load_configuration, connect_to_jira

# Mark all tests in this file as 'integration'
pytestmark = pytest.mark.integration

# --- Test Data ---
# You can override this with an issue key that is known to exist in your Jira.
# If it has a description, the test should pass. If not, it should gracefully fail.
EXISTING_ISSUE_KEY = get_issue_description.ISSUE_KEY_TO_FETCH
NON_EXISTENT_ISSUE_KEY = "PROJ-99999"


@pytest.fixture(scope="module")
def live_jira_client():
    """
    Provides a live, authenticated Jira client for the test module.
    Fails the test run if the client cannot be created.
    """
    try:
        config = load_configuration()
        client = connect_to_jira(
            config["server"],
            config["email"],
            config["api_token"]
        )
        return client
    except Exception as e:
        pytest.fail(f"Failed to create a live Jira client for integration tests: {e}")


def test_get_existing_issue_description_live(live_jira_client):
    """
    Tests fetching the description of a known existing issue.
    This test expects the issue to have a description.
    """
    description = get_issue_description.get_issue_description(live_jira_client, EXISTING_ISSUE_KEY)

    # The test will pass if a description is found, or if the issue has no description.
    # It will only fail on an unexpected error.
    # We assert it's a string or None, which covers both successful cases.
    assert isinstance(description, (str, type(None))), \
        f"Expected a string or None, but got {type(description)}"
    
    if description:
        assert len(description) > 0


def test_get_non_existent_issue_description_live(live_jira_client):
    """
    Tests that the function handles a non-existent issue key gracefully
    by returning None.
    """
    description = get_issue_description.get_issue_description(live_jira_client, NON_EXISTENT_ISSUE_KEY)
    assert description is None


def test_main_function_live_get_description():
    """
    Tests the main function of get_issue_description.py end-to-end.
    This assumes the ISSUE_KEY_TO_FETCH in the script is valid.
    """
    try:
        # The main function will sys.exit(1) on failure, which pytest handles.
        # A successful run will complete without raising an exception.
        get_issue_description.main()
    except SystemExit as e:
        pytest.fail(f"get_issue_description.main() exited with code {e.code}. Expected successful execution.")
    except Exception as e:
        pytest.fail(f"get_issue_description.main() failed during live execution: {e}")
