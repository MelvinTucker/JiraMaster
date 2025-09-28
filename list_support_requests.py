"""list_support_requests.py
==========================

A utility to connect to a Jira instance, search for the last 10 created
'Support Request' issues using a JQL query, and print the results to the
console with enhanced visual formatting using the 'rich' library.

This script uses Loguru for logging, python-dotenv for configuration
management, and the jira library to interact with the Jira API.

Core Features:
- Securely loads credentials and a JQL query from a .env file.
- Connects to a Jira instance.
- Searches for issues using the provided JQL.
- Prints a formatted list of issues (ID and Summary) to the console.
- Handles errors gracefully, including invalid JQL queries.
- Provides colorized console logging and file-based logging via Loguru.

Dependencies:
    - jira
    - python-dotenv
    - loguru
    - rich

Usage:
    Ensure a `.env` file exists with the required variables. Then run:

        python list_support_requests.py
"""

import os
import sys

from dotenv import load_dotenv
from jira import JIRA
from jira.exceptions import JIRAError
from loguru import logger
from rich.console import Console
from rich.table import Table
import requests

# --- Configuration ---
LOG_FILE = "list_support_requests.log"

# --- Functions ---

def configure_logging():
    """
    Configures Loguru to log to both console and a file.
    """
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    logger.add(
        LOG_FILE,
        level="DEBUG",
        rotation="10 MB",
        retention="10 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )

def load_configuration() -> dict:
    """
    Loads Jira configuration from the .env file.

    Returns:
        A dictionary with 'url', 'user', 'api_token', and 'jql_query'.

    Raises:
        EnvironmentError: If any required environment variables are missing.
    """
    logger.info("Loading configuration from .env file...")
    load_dotenv()

    config_vars = {
        "url": os.getenv("JIRA_URL"),
        "user": os.getenv("JIRA_USER"),
        "api_token": os.getenv("JIRA_API_TOKEN"),
        "jql_query": os.getenv("JIRA_JQL_QUERY")
    }

    missing = [key.upper() for key, value in config_vars.items() if not value]
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.critical(error_msg)
        raise EnvironmentError(error_msg)

    logger.success("Configuration loaded successfully.")
    return config_vars

    # This function is no longer needed for the primary logic of this script,
    # but is kept for potential future use or as a reference.
    pass

def search_and_print_issues(url: str, user: str, api_token: str, jql_query: str):
    """
    Searches for Jira issues using a direct `requests` call to the v3 API,
    filters for issues with .msg attachments, and prints them to the console.

    Args:
        url: The base URL of the Jira instance.
        user: The email address or username for authentication.
        api_token: The API token for authentication.
        jql_query: The JQL query string to execute.
    """
    console = Console()
    logger.info(f"Searching for issues with JQL: '{jql_query}' using direct 'requests' call.")

    search_url = f"{url}/rest/api/3/search/jql"
    auth = (user, api_token)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "jql": jql_query,
        "maxResults": 50,  # Fetch 50 most recent issues
        "fields": ["summary", "status", "created", "attachment"]  # Ensure attachment field is requested
    }

    try:
        response = requests.post(search_url, headers=headers, auth=auth, json=payload, timeout=30)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

        issues = response.json().get("issues", [])

        # Filter issues for .msg attachments
        filtered_issues = []
        for issue in issues:
            attachments = issue.get("fields", {}).get("attachment", [])
            if any(att.get("filename", "").lower().endswith(".msg") for att in attachments):
                filtered_issues.append(issue)
        
        logger.info(f"Found {len(issues)} issues, filtered down to {len(filtered_issues)} with .msg attachments.")

        if not filtered_issues:
            console.print("\n[yellow]No recent support requests with .msg attachments found.[/yellow]\n")
            return

        table = Table(title="Support Requests with .msg Attachments", show_header=True, header_style="bold magenta")
        table.add_column("Issue Key", style="dim", width=12)
        table.add_column("Summary")
        table.add_column("Status", justify="right")
        table.add_column("Created", justify="right")

        for issue in filtered_issues:
            fields = issue.get("fields", {})
            key = issue.get("key")
            summary = fields.get("summary", "No summary")
            status = fields.get("status", {}).get("name", "N/A")
            created = fields.get("created", "N/A").split("T")[0]
            table.add_row(key, summary, status, created)

        console.print(table)

    except requests.exceptions.HTTPError as e:
        error_text = e.response.text
        error_msg = f"HTTP error during search: {e.response.status_code} {e.response.reason}. Response: {error_text}"
        logger.error(error_msg)
        console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        error_msg = f"A network error occurred: {e}"
        logger.error(error_msg)
        console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
        sys.exit(1)

def main():
    """
    Main execution function for the script.
    """
    configure_logging()
    try:
        config = load_configuration()
        # We no longer need to create a jira client for this script's main function.
        # We pass the config directly to the search function.
        search_and_print_issues(
            url=config["url"],
            user=config["user"],
            api_token=config["api_token"],
            jql_query=config["jql_query"]
        )

    except EnvironmentError as e:
        console = Console()
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("An unexpected error occurred during execution.")
        sys.exit(1)
    
    return 0


if __name__ == "__main__":
    main()
