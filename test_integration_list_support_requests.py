"""Integration tests for the list_support_requests module.

This test suite validates the list_support_requests script against live
services, including Jira and a local LM Studio instance, using the
configuration from the .env file.

It specifically tests the refactored functionality of loading AI prompts
from external .txt files and the new three-step summarization workflow.

Usage:
    pytest -m integration
"""

import os
import pytest
import list_support_requests

# Mark all tests in this file as 'integration'
pytestmark = pytest.mark.integration

# --- Test Configuration ---
KNOWN_ISSUE_WITH_ATTACHMENT = "ICISTWO-34338"
PROMPT_TEMPLATES_DIR = "prompt_templates"
DESCRIPTION_PROMPT_FILE = os.path.join(PROMPT_TEMPLATES_DIR, "description_summary_prompt.txt")
EMAIL_PROMPT_FILE = os.path.join(PROMPT_TEMPLATES_DIR, "email_summary_prompt.txt")
COMPREHENSIVE_PROMPT_FILE = os.path.join(PROMPT_TEMPLATES_DIR, "comprehensive_summary_prompt.txt")


@pytest.fixture
def single_issue_jql_query():
    """
    Overrides the JQL query in the environment to fetch only the specific
    known issue for this test.
    """
    original_jql = os.environ.get("JIRA_JQL_QUERY")
    test_jql = f"issueKey = '{KNOWN_ISSUE_WITH_ATTACHMENT}'"
    
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("JIRA_JQL_QUERY", test_jql)
        yield


def test_prompt_template_files_exist():
    """Verify that all three prompt template files exist."""
    assert os.path.isdir(PROMPT_TEMPLATES_DIR), f"Directory not found: {PROMPT_TEMPLATES_DIR}"
    assert os.path.isfile(DESCRIPTION_PROMPT_FILE), f"File not found: {DESCRIPTION_PROMPT_FILE}"
    assert os.path.isfile(EMAIL_PROMPT_FILE), f"File not found: {EMAIL_PROMPT_FILE}"
    assert os.path.isfile(COMPREHENSIVE_PROMPT_FILE), f"File not found: {COMPREHENSIVE_PROMPT_FILE}"


def test_process_issues_live_e2e_three_step_summary(single_issue_jql_query):
    """
    Tests the process_issues function end-to-end, validating the three-step
    summarization workflow against live services.
    
    This test performs the following checks:
    1. Verifies that all required prompt template files exist.
    2. Loads configuration and connects to the live LM Studio instance.
    3. Calls the `process_issues` function to fetch and process a single known issue.
    4. Asserts that the function returns data for one issue.
    5. Asserts that three non-empty summaries ('desc_summary', 'email_summary',
       and 'comprehensive_summary') are present in the result.
    """
    # 1. Verify prompt files exist before running the main logic
    test_prompt_template_files_exist()

    try:
        # 2. Set up live connections
        config = list_support_requests.load_configuration()
        lm_client = list_support_requests.test_lm_studio_connection(
            base_url=config["lm_studio_base_url"], api_key=config["lm_studio_api_key"]
        )

        # 3. Call the core processing function
        processed_data = list_support_requests.process_issues(config, lm_client)

        # 4. Assert on the results
        assert processed_data is not None, "process_issues should return a list, not None."
        assert len(processed_data) == 1, f"Expected to process 1 issue, but got {len(processed_data)}."

        issue_result = processed_data[0]
        assert issue_result["key"] == KNOWN_ISSUE_WITH_ATTACHMENT

        # 5. Assert that all three summaries are present and non-empty
        assert "desc_summary" in issue_result and issue_result["desc_summary"], "Description summary is missing or empty."
        assert "email_summary" in issue_result and issue_result["email_summary"], "Email summary is missing or empty."
        assert "comprehensive_summary" in issue_result and issue_result["comprehensive_summary"], "Comprehensive summary is missing or empty."

        assert "Error" not in issue_result["desc_summary"]
        assert "Error" not in issue_result["email_summary"]
        assert "Error" not in issue_result["comprehensive_summary"]

    except Exception as e:
        pytest.fail(f"Live test of process_issues failed during execution: {e}")



