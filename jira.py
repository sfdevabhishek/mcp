import requests
from requests.auth import HTTPBasicAuth
import json
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL")
JIRA_EMAIL    = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

def create_jira_issue(
    summary: str,
    description: str,
    project_key: str,
    issue_type: str = "Task",
    priority: str = "Medium",
    assignee_email: str = None,
    labels: list = None,
    sf_case_id: str = None,
) -> dict:
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Build ADF description, optionally appending SF case reference
    description_content = [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": description}],
        }
    ]
    if sf_case_id:
        description_content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": f"Salesforce Case ID: {sf_case_id}"}],
        })

    fields = {
        "project":     {"key": project_key},
        "summary":     summary,
        "description": {
            "type":    "doc",
            "version": 1,
            "content": description_content,
        },
        "issuetype": {"name": issue_type},
        "priority":  {"name": priority},
    }

    if labels:
        fields["labels"] = labels

    # Resolve assignee account ID from email if provided
    if assignee_email:
        account_id = _get_account_id(assignee_email, auth)
        if account_id:
            fields["assignee"] = {"accountId": account_id}

    payload = json.dumps({"fields": fields})

    response = requests.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue",
        data=payload,
        headers=headers,
        auth=auth,
        verify=False,
    )

    data = response.json()

    if not response.ok:
        errors = data.get("errors", {})
        messages = data.get("errorMessages", [])
        raise Exception(f"Jira API error {response.status_code}: {errors or messages}")

    issue_key = data["key"]
    issue_url = f"{JIRA_BASE_URL}/browse/{issue_key}"

    return {
        "success":   True,
        "issue_key": issue_key,
        "issue_url": issue_url,
        "message":   f"Jira issue {issue_key} created successfully",
    }


def _get_account_id(email: str, auth: HTTPBasicAuth) -> str | None:
    """Look up a Jira user's accountId by email. Returns None if not found."""
    response = requests.get(
        f"{JIRA_BASE_URL}/rest/api/3/user/search",
        params={"query": email},
        headers={"Accept": "application/json"},
        auth=auth,
        verify=False,
    )
    users = response.json() if response.ok else []
    return users[0]["accountId"] if users else None