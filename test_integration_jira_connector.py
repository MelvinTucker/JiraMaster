"""Integration tests for the jira_connector module.

This test suite validates the Jira connector's functionality against a live
Jira instance. It requires a valid .env file with credentials.

These tests are marked as 'integration' and should be run selectively
if you do not want to impact the live system.

Usage:
    - Run all tests:
        pytest

    - Run only integration tests:
        pytest -m integration
"""

from unittest.mock import patch
import pytest

# Module under test
import jira_connector

# Mark all tests in this file as 'integration'
pytestmark = pytest.mark.integration


def test_load_configuration_live():
    """
    Tests that the configuration is loaded correctly from the .env file.
    This is a precondition for all other live tests.
    """
    try:
        config = jira_connector.load_configuration()
        assert "server" in config
        assert "email" in config
        assert "api_token" in config
        assert all(config.values())  # Ensure no value is empty
    except (FileNotFoundError, EnvironmentError) as e:
        pytest.fail(f"Failed to load configuration for live tests: {e}")


def test_connect_to_jira_live():
    """
    Tests a real connection to the Jira instance specified in the .env file.
    """
    # Load configuration from .env
    config = jira_connector.load_configuration()

    # Attempt to connect
    try:
        client = jira_connector.connect_to_jira(
            server=config["server"],
            email=config["email"],
            api_token=config["api_token"]
        )
        # A successful connection should return a client object
        assert client is not None
        # Validate by fetching current user, which requires a valid connection
        assert client.current_user() is not None
    except Exception as e:
        pytest.fail(f"Live Jira connection failed: {e}")


@patch('sys.argv', ['jira_connector.py'])
def test_main_function_live():
    """
    Tests the main function to ensure it runs end-to-end without errors.
    """
    try:
        # The main function should execute and return 0 on success
        exit_code = jira_connector.main()
        assert exit_code == 0
    except Exception as e:
        pytest.fail(f"The main function failed during live execution: {e}")
