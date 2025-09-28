"""Unit tests for the list_support_requests module.

This test suite validates the list_support_requests script's core logic,
focusing on the AI summarization feature by mocking external services
like the OpenAI client.

Usage:
    pytest
"""

from unittest.mock import patch, MagicMock
import pytest
from openai import OpenAI

# Module under test
import list_support_requests

# This file now contains unit tests, so the 'integration' mark is removed.


@patch("list_support_requests.OpenAI")
def test_test_lm_studio_connection_success(mock_openai):
    """Tests a successful connection to the LM Studio server."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    client = list_support_requests.test_lm_studio_connection("base_url", "api_key")
    
    mock_openai.assert_called_once_with(base_url="base_url", api_key="api_key")
    client.models.list.assert_called_once()


@patch("list_support_requests.OpenAI", side_effect=Exception("Connection failed"))
def test_test_lm_studio_connection_failure(mock_openai):
    """Tests a failed connection to the LM Studio server."""
    with pytest.raises(ConnectionError, match="Failed to connect to LM Studio server"):
        list_support_requests.test_lm_studio_connection("base_url", "api_key")


def test_get_summary_from_lm_studio_success():
    """
    Tests the summarization function by mocking the OpenAI client's
    chat completions method.
    """
    mock_client = MagicMock()
    
    # Configure the mock to handle the nested attribute access
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = " This is a test summary. "
    mock_client.chat.completions.create.return_value = mock_completion

    model = "test-model"
    description = "This is a long issue description."
    
    summary = list_support_requests.get_summary_from_lm_studio(mock_client, model, description)

    # Assert that the summary is correct and stripped of whitespace
    assert summary == "This is a test summary."

    # Assert that the API was called with the correct parameters
    mock_client.chat.completions.create.assert_called_once_with(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are Melvin Tucker, an expert technical support analyst. Your task is to provide a concise, narrative summary of the following text, speaking in the first person as if you are explaining your findings.",
            },
            {"role": "user", "content": description},
        ],
        temperature=0.7,
    )


def test_get_summary_from_lm_studio_api_error():
    """Tests that the summarization function handles an API error gracefully."""
    mock_client = MagicMock()
    error_message = "API rate limit exceeded"
    
    # Configure the mock to raise an exception on the nested call
    mock_client.chat.completions.create.side_effect = Exception(error_message)

    summary = list_support_requests.get_summary_from_lm_studio(mock_client, "model", "desc")
    
    assert f"Error generating summary: {error_message}" in summary


@patch('sys.argv', ['list_support_requests.py'])
@patch('list_support_requests.load_configuration')
@patch('list_support_requests.test_lm_studio_connection')
@patch('list_support_requests.process_issues')
def test_main_function_full_run(mock_process, mock_test_conn, mock_load_config):
    """
    Tests the main function's orchestration of loading config, testing connection,
    and processing issues.
    """
    # Mock the return values of the patched functions
    mock_config = {
        "lm_studio_base_url": "http://fake-url:1234",
        "lm_studio_api_key": "fake-key"
    }
    mock_load_config.return_value = mock_config
    
    mock_lm_client = MagicMock()
    mock_test_conn.return_value = mock_lm_client
    
    # Mock the return value of the core processing function
    mock_process.return_value = [
        {"key": "TEST-1", "title": "Test Issue", "desc_summary": "Summary 1", "email_summary": "Summary 2"}
    ]
    
    # Run the main function
    exit_code = list_support_requests.main()

    # Assert that the main function ran successfully
    assert exit_code == 0
    
    # Assert that the configuration was loaded
    mock_load_config.assert_called_once()
    
    # Assert that the LM Studio connection was tested with the correct config
    mock_test_conn.assert_called_once_with(
        base_url=mock_config["lm_studio_base_url"],
        api_key=mock_config["lm_studio_api_key"]
    )
    
    # Assert that the process function was called with the config and the client
    mock_process.assert_called_once_with(mock_config, mock_lm_client)
