"""list_support_requests.py
==========================

Connects to Jira, fetches recent 'Support Request' issues with .msg attachments,
generates an AI summary for each issue's description using a local LM Studio
instance, and prints the results to the console.

Core Features:
- Securely loads credentials for Jira and settings for an OpenAI-compatible API.
- Tests the connection to the local AI model server before proceeding.
- Fetches the 50 most recent support requests.
- Filters issues to find those with .msg attachments.
- For each filtered issue, generates a concise summary of its description using a local AI model.
- Displays the results in a clean, readable format using rich panels.
- Provides robust, colorized logging via Loguru.

Dependencies:
    - jira
    - python-dotenv
    - loguru
    - rich
    - openai

Usage:
    1. Ensure your local AI model server (e.g., LM Studio) is running.
    2. Ensure a `.env` file exists with the required variables.
    3. Run the script:
        python list_support_requests.py
"""

import os
import sys
import tempfile
import extract_msg

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import requests

# --- Configuration ---
LOG_FILE = "list_support_requests.log"


# --- Functions ---

def configure_logging():
    """Configures Loguru for console and file logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        LOG_FILE,
        level="DEBUG",
        rotation="10 MB",
        retention="10 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )


def load_configuration() -> dict:
    """
    Loads Jira and LM Studio configuration from the .env file.

    Returns:
        A dictionary containing all required configuration variables.

    Raises:
        EnvironmentError: If any required environment variables are missing.
    """
    logger.info("Loading configuration from .env file...")
    load_dotenv()

    config_vars = {
        "url": os.getenv("JIRA_URL"),
        "user": os.getenv("JIRA_USER"),
        "api_token": os.getenv("JIRA_API_TOKEN"),
        "jql_query": os.getenv("JIRA_JQL_QUERY"),
        "lm_studio_base_url": os.getenv("LM_STUDIO_BASE_URL"),
        "lm_studio_api_key": os.getenv("LM_STUDIO_API_KEY"),
        "lm_studio_model": os.getenv("LM_STUDIO_MODEL"),
    }

    missing = [key.upper() for key, value in config_vars.items() if not value]
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.critical(error_msg)
        raise EnvironmentError(error_msg)

    logger.success("Configuration loaded successfully.")
    return config_vars


def test_lm_studio_connection(base_url: str, api_key: str) -> OpenAI:
    """
    Tests the connection to the LM Studio server and returns a client.

    Args:
        base_url: The base URL of the LM Studio server.
        api_key: The API key for the server.

    Returns:
        An initialized OpenAI client if the connection is successful.

    Raises:
        ConnectionError: If the client cannot connect or list models.
    """
    logger.info(f"Testing connection to LM Studio at {base_url}...")
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        
        # A simple check to verify connectivity and get server models
        response = client.models.list()
        
        # Log the models found for debugging purposes
        model_names = [model.id for model in response.data]
        logger.debug(f"Found models on LM Studio server: {model_names}")
        
        logger.success("LM Studio connection successful.")
        return client
    except Exception as e:
        # Log the full error with traceback for better diagnostics
        logger.error(f"Failed to connect to LM Studio server. Is it running? Full error: {e}", exc_info=True)
        
        # Attempt to provide a more specific error message
        error_details = str(e)
        if "Failed to parse" in error_details or "Expecting value" in error_details:
            error_msg = (
                "Failed to connect to LM Studio: The server returned an invalid response. "
                "This might be an HTML error page instead of a JSON response. "
                "Please check the LM Studio server logs."
            )
        else:
            error_msg = f"Failed to connect to LM Studio server. Is it running? Error: {e}"
            
        logger.critical(error_msg)
        raise ConnectionError(error_msg) from e


def get_description_text(description_field: dict) -> str:
    """
    Safely extracts the text content from a Jira rich text description field.

    Args:
        description_field: The 'description' field from the Jira API response.

    Returns:
        The concatenated text from the description, or a default message if empty.
    """
    if not description_field or 'content' not in description_field:
        return "No description available."

    text_parts = []
    try:
        for block in description_field.get('content', []):
            if 'content' in block:
                for item in block.get('content', []):
                    if 'text' in item:
                        text_parts.append(item['text'])
        
        full_text = "\n".join(text_parts).strip()
        return full_text if full_text else "No description available."
    except (TypeError, IndexError) as e:
        logger.warning(f"Could not parse description field, returning empty. Error: {e}")
        return "No description available."


def get_summary_from_lm_studio(client: OpenAI, model: str, description: str) -> str:
    """
    Generates a summary of a Jira issue description using the local AI model.

    Args:
        client: An authenticated OpenAI client.
        model: The model name to use for the completion.
        description: The Jira issue description text.

    Returns:
        The AI-generated summary as a string, or an error message.
    """
    if not description or not description.strip():
        return "No text provided to summarize."

    logger.info(f"Generating summary with model '{model}'...")
    try:
        completion = client.chat.completions.create(
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
        summary = completion.choices[0].message.content
        logger.success("Successfully generated summary.")
        return summary.strip() if summary else "Summary was empty."
    except Exception as e:
        logger.error(f"Failed to generate summary from LM Studio: {e}")
        return f"Error generating summary: {e}"


def process_issues(config: dict, lm_client: OpenAI) -> list[dict]:
    """
    Searches for Jira issues, downloads attachments, generates summaries,
    and returns a list of processed issue data.

    Args:
        config: The application configuration dictionary.
        lm_client: The initialized OpenAI client for summarization.

    Returns:
        A list of dictionaries, where each dictionary contains the
        issue key, title, and the two generated summaries.
    """
    console = Console()
    processed_data = []
    logger.info(f"Searching for issues with JQL: '{config['jql_query']}'...")

    search_url = f"{config['url']}/rest/api/3/search/jql"
    auth = (config["user"], config["api_token"])
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jql": config["jql_query"],
        "maxResults": 50,
        "fields": ["summary", "attachment", "description"],
    }

    try:
        response = requests.post(
            search_url, headers=headers, auth=auth, json=payload, timeout=30
        )
        response.raise_for_status()
        issues = response.json().get("issues", [])

        issues_with_msg = []
        for issue in issues:
            attachments = issue.get("fields", {}).get("attachment", [])
            msg_attachments = [
                att for att in attachments if att.get("filename", "").lower().endswith(".msg")
            ]
            if msg_attachments:
                issue['msg_attachment'] = msg_attachments[0]
                issues_with_msg.append(issue)

        logger.info(
            f"Found {len(issues)} issues, filtered down to {len(issues_with_msg)} with .msg attachments."
        )

        if not issues_with_msg:
            console.print(
                "\n[yellow]No recent support requests with .msg attachments found.[/yellow]\n"
            )
            return processed_data

        for issue in issues_with_msg:
            fields = issue.get("fields", {})
            key = issue.get("key")
            summary_title = fields.get("summary", "No summary")
            description = get_description_text(fields.get("description"))

            desc_summary = get_summary_from_lm_studio(
                client=lm_client,
                model=config["lm_studio_model"],
                description=description,
            )

            email_summary = "Could not process email attachment."
            attachment_meta = issue['msg_attachment']
            attachment_url = attachment_meta.get("content")
            
            if attachment_url:
                tmp_file_path = None
                try:
                    logger.info(f"Downloading attachment: {attachment_meta.get('filename')}")
                    att_response = requests.get(attachment_url, auth=auth, timeout=30)
                    att_response.raise_for_status()

                    # Create a temporary file but keep it closed so other processes can access it on Windows.
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".msg") as tmp:
                        tmp.write(att_response.content)
                        tmp_file_path = tmp.name
                    
                    logger.info(f"Parsing email content from temporary file: {tmp_file_path}")
                    msg = None
                    try:
                        msg = extract_msg.Message(tmp_file_path)
                        email_body = msg.body
                        
                        email_summary = get_summary_from_lm_studio(
                            client=lm_client,
                            model=config["lm_studio_model"],
                            description=email_body,
                        )
                    finally:
                        if msg and hasattr(msg, 'close'):
                            msg.close() # Ensure the file handle is released by extract-msg
                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to download attachment for {key}: {e}")
                    email_summary = "Error: Failed to download attachment."
                except Exception as e:
                    logger.error(f"Failed to parse .msg file for {key}: {e}", exc_info=True)
                    email_summary = "Error: Failed to parse email file."
                finally:
                    # Manually clean up the temporary file
                    if tmp_file_path and os.path.exists(tmp_file_path):
                        os.remove(tmp_file_path)
            
            processed_data.append({
                "key": key,
                "title": summary_title,
                "desc_summary": desc_summary,
                "email_summary": email_summary,
            })

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
        
    return processed_data


def main():
    """Main execution function for the script."""
    configure_logging()
    console = Console()
    try:
        config = load_configuration()

        lm_client = test_lm_studio_connection(
            base_url=config["lm_studio_base_url"], api_key=config["lm_studio_api_key"]
        )

        processed_issues = process_issues(config, lm_client)

        for issue_data in processed_issues:
            title = f"[bold magenta]{issue_data['key']}[/bold magenta] - {issue_data['title']}"
            summary_text = Text()
            summary_text.append("AI Summary (Description): ", style="cyan")
            summary_text.append(f"{issue_data['desc_summary']}\n", style="italic")
            summary_text.append("AI Summary (Email): ", style="cyan")
            summary_text.append(issue_data['email_summary'], style="italic")
            console.print(Panel(summary_text, title=title, border_style="green", expand=False))

    except (EnvironmentError, ConnectionError) as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("An unexpected error occurred during execution.")
        console.print(f"\n[bold red]An unexpected error occurred. Check {LOG_FILE} for details.[/bold red]")
        sys.exit(1)

    return 0


if __name__ == "__main__":
    main()
