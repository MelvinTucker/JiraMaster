"""jira_connector.py
=====================

Utility to establish and validate a connection to a Jira instance.

This module loads Jira connection configuration from a .env file using
python-dotenv and attempts to authenticate with Jira using the `jira`
library. It validates the connection by fetching the current user and
server info. Logging is configured to write to both the console and a
file named `jira_connector.log`.

Dependencies:
    - jira
    - python-dotenv

Usage:
    Ensure a `.env` file exists with the variables documented in
    `.env.example`. Then run:

        python jira_connector.py

Security:
    Do not hardcode credentials in this file. Keep secrets in environment
    variables or a secured secrets store. The included `.env.example`
    shows the needed environment variable names.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from dotenv import load_dotenv, find_dotenv
from jira import JIRA
from jira.exceptions import JIRAError
import requests

LOG_FILENAME = "jira_connector.log"
MAX_LOG_BYTES = 1024 * 1024  # 1 MB
LOG_BACKUP_COUNT = 5


def configure_logging(
    log_file: str = LOG_FILENAME,
    verbose: bool = False,
) -> None:
    """Configure logging to console and a rotating file.

    Args:
        log_file: Path to the logfile.
        verbose: If True, set log level to DEBUG, otherwise INFO.

    Returns:
        None
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger()
    logger.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Rotating file handler
    fh = RotatingFileHandler(
        log_file, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    fh.setLevel(log_level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def load_configuration(dotenv_path: Optional[str] = None) -> dict:
    """Load Jira configuration from a .env file.

    This function will attempt to locate a .env file automatically if a
    path is not supplied. It requires the following variables to be set:

    - JIRA_URL
    - JIRA_USER
    - JIRA_API_TOKEN

    Args:
        dotenv_path: Optional path to a .env file. If None, find_dotenv()
                     will be used to locate it.

    Returns:
        A dict with keys 'server', 'email', 'api_token'.

    Raises:
        FileNotFoundError: If .env file cannot be found.
        EnvironmentError: If any required variable is missing.
    """
    logging.info("Loading environment variables")

    # If a path isn't provided, try to locate one in the project tree
    if dotenv_path is None:
        dotenv_path = find_dotenv()
        
    if not dotenv_path:
        logging.error("No .env file found. Please create one based on .env.example")
        raise FileNotFoundError("Missing .env file")

    # Load the environment variables from the file into the environment
    loaded = load_dotenv(dotenv_path)
    if not loaded:
        logging.error("Failed to load .env file at %s", dotenv_path)
        raise FileNotFoundError(f"Could not load .env file at {dotenv_path}")

    server = os.getenv("JIRA_URL")
    email = os.getenv("JIRA_USER")
    api_token = os.getenv("JIRA_API_TOKEN")

    missing = [name for name, val in [("JIRA_URL", server), ("JIRA_USER", email), ("JIRA_API_TOKEN", api_token)] if not val]

    if missing:
        logging.error("Missing required environment variables: %s", ", ".join(missing))
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    return {"server": server, "email": email, "api_token": api_token}


def connect_to_jira(server: str, email: str, api_token: str, timeout: int = 30) -> JIRA:
    """Attempt to connect to a Jira server using the provided credentials.

    Args:
        server: Base URL of the Jira server (e.g., https://your-domain.atlassian.net).
        email: User email for the account.
        api_token: API token for authentication.
        timeout: Network timeout in seconds for the HTTP requests.

    Returns:
        An authenticated `JIRA` client instance.

    Raises:
        requests.exceptions.RequestException: Network related errors (DNS, timeout, etc.).
        PermissionError: When authentication fails.
        JIRAError: Other JIRA related errors.
    """
    logging.info("Attempting to connect to Jira server at %s", server)

    try:
        # Standard, simple client instantiation.
        jira_client = JIRA(
            server=server,
            basic_auth=(email, api_token),
            timeout=timeout
        )

        # Validate by fetching the current user (non-destructive)
        current_user = jira_client.current_user()
        server_info = jira_client.server_info()

        logging.info("Connection successful. Current user: %s. Jira version: %s", current_user, server_info.get("version"))
        return jira_client

    except JIRAError as e:
        # JIRAError covers many API-level errors including auth failures
        status_code = getattr(e, 'status_code', None)
        logging.error("JIRAError while connecting: %s", e, exc_info=True)
        if status_code in (401, 403):
            raise PermissionError("Authentication failed. Check JIRA_USER_EMAIL and JIRA_API_TOKEN.") from e
        raise
    except requests.exceptions.RequestException as e:
        # network-related problems (timeout, DNS failures, connection errors)
        logging.error("Network error when connecting to Jira: %s", e, exc_info=True)
        raise


def main() -> int:
    """Main entrypoint for the script.

    Loads configuration, attempts to connect to Jira, and prints a
    success or failure message to stdout. Returns an exit code suitable
    for use in shell scripts (0 == success, non-zero == failure).

    Returns:
        int: Exit code (0 success, 1 failure).
    """
    parser = argparse.ArgumentParser(description="Jira Connection Utility")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )
    args = parser.parse_args()

    configure_logging(verbose=args.verbose)

    try:
        cfg = load_configuration()
    except FileNotFoundError as e:
        print("Configuration error: .env file not found. See .env.example to create one.")
        logging.error("%s", e, exc_info=True)
        return 1
    except EnvironmentError as e:
        print(f"Configuration error: {e}")
        logging.error("%s", e, exc_info=True)
        return 1

    try:
        client = connect_to_jira(cfg["server"], cfg["email"], cfg["api_token"])
        print("Jira connection successful.")
        return 0
    except PermissionError as e:
        print("Authentication failed: please verify your email and API token in the .env file.")
        logging.error("%s", e, exc_info=True)
        return 1
    except requests.exceptions.RequestException as e:
        print(f"Network error when connecting to Jira: {e}")
        logging.error("%s", e, exc_info=True)
        return 1
    except JIRAError as e:
        print(f"Jira API error: {e}")
        logging.error("%s", e, exc_info=True)
        return 1
    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Unexpected error: {e}")
        logging.error("Unexpected error", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
