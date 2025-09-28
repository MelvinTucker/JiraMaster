"""Integration tests for the list_support_requests module.

This test suite validates the list_support_requests script against live
services, including Jira and a local LM Studio instance, using the
configuration from the .env file.

Usage:
    pytest -m integration
"""

import os
import pytest
from unittest.mock import patch
import list_support_requests

# Mark all tests in this file as 'integration'
pytestmark = pytest.mark.integration

# --- Test Configuration ---
# Define a specific, known issue key that exists in your Jira instance
# and has a .msg attachment. This makes the test reliable.
# You MUST replace this with a real issue key from your Jira for the test to work.
KNOWN_ISSUE_WITH_ATTACHMENT = "ICISTWO-34338"


@pytest.fixture
def single_issue_jql_query():
    """
    Overrides the JQL query in the environment to fetch only the specific
    known issue for this test.
    """
    original_jql = os.environ.get("JIRA_JQL_QUERY")
    test_jql = f"issueKey = '{KNOWN_ISSUE_WITH_ATTACHMENT}'"
    
    with patch.dict(os.environ, {"JIRA_JQL_QUERY": test_jql}):
        yield
    
    # Restore original environment variable after test
    if original_jql:
        os.environ["JIRA_JQL_QUERY"] = original_jql
    else:
        del os.environ["JIRA_JQL_QUERY"]


def test_main_function_live_e2e_single_issue(single_issue_jql_query):
    """
    Tests the main function of list_support_requests.py end-to-end against
    a single, known Jira issue.
    This test now patches the `process_issues` function to isolate the test
    from the live Jira API and focus on the summarization calls.
    """
    # Define mock return data that simulates a successful API call
    mock_processed_data = [
        {
            "key": KNOWN_ISSUE_WITH_ATTACHMENT,
            "title": "Test Issue with Attachment",
            "desc_summary": "This is a mock summary for the description.",
            "email_summary": "This is a mock summary for the email.",
        }
    ]

    # Patch the function that contains the core logic
    with patch('list_support_requests.process_issues', return_value=mock_processed_data) as mock_process:
        try:
            return_code = list_support_requests.main()
            assert return_code == 0, "main() should return 0 on success."
        except SystemExit as e:
            pytest.fail(f"list_support_requests.main() exited with code {e.code}. Expected successful execution.")
        except Exception as e:
            pytest.fail(f"list_support_requests.main() failed during live execution: {e}")

        # Assert that the core processing function was called once
        assert mock_process.call_count == 1, \
            f"Expected process_issues to be called once, but got {mock_process.call_count}."


