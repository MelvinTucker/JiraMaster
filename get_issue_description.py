"""get_issue_description.py
===========================

A utility to connect to a Jira instance, retrieve a specific issue,
and print its description to the console.

This script uses Loguru for logging, python-dotenv for configuration
management, and the jira library to interact with the Jira API.

Core Features:
- Securely loads credentials from a .env file.
- Connects to a Jira instance.
- Fetches a specific issue by its key.
- Prints the issue's description.
- Handles errors gracefully, especially for missing issues (404).
- Provides colorized console logging and file-based logging via Loguru.

Dependencies:
    - jira
    - python-dotenv
    - loguru

Usage:
    Ensure a `.env` file exists with the required variables. Then run:

        python get_issue_description.py
"""

import os
import sys

from dotenv import load_dotenv
from jira import JIRA
from jira.exceptions import JIRAError
from loguru import logger
import requests

# --- Configuration ---
# The script will look for a .env file in the project root.
# Ensure it contains: JIRA_URL, JIRA_USER, JIRA_API_TOKEN
ISSUE_KEY_TO_FETCH = "ICISTWO-34337"
LOG_FILE = "get_issue_description.log"

# --- Functions ---

def configure_logging():
    """
    Configures Loguru to log to both console and a file.
    Console logs are colorized. File logs are rotated.
    """
    logger.remove()  # Remove default handler
    # Console logger
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    # File logger
    logger.add(
        LOG_FILE,
        level="DEBUG",
        rotation="10 MB",
        retention="10 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,  # Make logging thread-safe
        backtrace=True,
        diagnose=True
    )

def load_configuration() -> dict:
    """
    Loads Jira configuration from the .env file.

    Returns:
        A dictionary with 'url', 'user', and 'api_token'.

    Raises:
        EnvironmentError: If any required environment variables are missing.
    """
    logger.info("Loading configuration from .env file...")
    load_dotenv()

    jira_url = os.getenv("JIRA_URL")
    jira_user = os.getenv("JIRA_USER")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_user, jira_api_token]):
        missing = [v for v, k in [("JIRA_URL", jira_url), ("JIRA_USER", jira_user), ("JIRA_API_TOKEN", jira_api_token)] if not k]
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.critical(error_msg)
        raise EnvironmentError(error_msg)

    logger.success("Configuration loaded successfully.")
    return {"url": jira_url, "user": jira_user, "api_token": jira_api_token}

def create_jira_client(url: str, user: str, api_token: str) -> JIRA:
    """
    Creates and authenticates a Jira client.

    Args:
        url: The base URL of the Jira instance.
        user: The email address or username for authentication.
        api_token: The API token for authentication.

    Returns:
        An authenticated JIRA client instance.

    Raises:
        ConnectionError: If authentication or connection fails.
    """
    logger.info(f"Attempting to connect to Jira at {url}...")
    try:
        # Standard, simple client instantiation.
        jira_client = JIRA(
            server=url,
            basic_auth=(user, api_token),
            timeout=20
        )
        # A lightweight check to confirm API access and authentication.
        jira_client.current_user()
        logger.success("Jira connection successful.")
        return jira_client
    except (JIRAError, requests.exceptions.RequestException) as e:
        error_msg = f"Failed to connect to Jira: {e}"
        logger.error(error_msg)
        if isinstance(e, JIRAError) and e.status_code in (401, 403):
             raise ConnectionError("Authentication failed. Please check your credentials in the .env file.") from e
        raise ConnectionError(error_msg) from e


def get_issue_description(client: JIRA, issue_key: str) -> str | None:
    """
    Retrieves the description of a specific Jira issue.

    Args:
        client: An authenticated Jira client.
        issue_key: The key of the issue to retrieve (e.g., 'PROJ-123').

    Returns:
        The issue's description as a string, or None if the issue
        is not found or an error occurs.
    """
    logger.info(f"Attempting to fetch issue '{issue_key}'...")
    try:
        issue = client.issue(issue_key)
        description = getattr(issue.fields, 'description', None)
        if description:
            logger.success(f"Successfully retrieved description for '{issue_key}'.")
            return description
        else:
            logger.warning(f"Issue '{issue_key}' found, but it has no description.")
            return None
    except JIRAError as e:
        if e.status_code == 404:
            logger.error(f"Issue '{issue_key}' not found or you lack permission to view it.")
        else:
            logger.error(f"A Jira API error occurred while fetching issue '{issue_key}': {e.text}")
        return None

def main():
    """
    Main execution function for the script.
    """
    configure_logging()
    try:
        config = load_configuration()
        jira_client = create_jira_client(
            url=config["url"],
            user=config["user"],
            api_token=config["api_token"]
        )
        description = get_issue_description(jira_client, ISSUE_KEY_TO_FETCH)

        if description:
            print("\n--- Jira Issue Description ---")
            print(description)
            print("----------------------------\n")
        else:
            print(f"Could not retrieve a description for issue '{ISSUE_KEY_TO_FETCH}'. Check logs for details.")
            sys.exit(1)

    except (EnvironmentError, ConnectionError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception("An unexpected error occurred.")
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
