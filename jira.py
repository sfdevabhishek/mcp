import requests
import json
import os
import urllib3
from auth import get_jira_auth
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL")

def create_jira_issue(
    summary: str,
    description: str,
    project_key: str = "KAN",
    issue_type: str = "Task",
    priority: str = "Medium",
    assignee_email: str = None,
    labels: list = None,
    sf_case_id: str = None,
) -> dict:
    auth = get_jira_auth()
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

def update_jira_issue_status(issue_key: str, status: str) -> dict:
    auth = get_jira_auth()   # ✅ from auth.py

    headers = {"Content-Type": "application/json"}
    transitions_url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions"

    # Step 1 — Get available transitions
    transitions_response = requests.get(transitions_url, auth=auth, headers=headers)
    transitions_response.raise_for_status()
    transitions = transitions_response.json().get("transitions", [])

    # Step 2 — Match requested status (case-insensitive)
    transition_id = None
    for t in transitions:
        if t["to"]["name"].lower() == status.lower():
            transition_id = t["id"]
            break

    if not transition_id:
        available = [t["to"]["name"] for t in transitions]
        return {
            "status":  "error",
            "message": f"Status '{status}' not found. Available transitions: {available}"
        }

    # Step 3 — Apply transition
    response = requests.post(transitions_url, auth=auth, headers=headers, json={"transition": {"id": transition_id}})
    response.raise_for_status()

    return {
        "status":  "success",
        "message": f"Jira issue {issue_key} moved to '{status}' successfully."
    }

def get_jira_issue(issue_key: str) -> dict:
    """
    Fetches the details of a Jira issue by its key.
    e.g. "ENG-101"
    """
    auth = get_jira_auth()

    headers = {"Content-Type": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"

    response = requests.get(url, auth=auth, headers=headers)
    response.raise_for_status()

    data = response.json()
    fields = data.get("fields", {})

    return {
        "status":      "success",
        "issue_key":   data["key"],
        "issue_url":   f"{JIRA_BASE_URL}/browse/{data['key']}",
        "summary":     fields.get("summary"),
        "description": fields.get("description"),
        "issue_type":  fields.get("issuetype", {}).get("name"),
        "priority":    fields.get("priority", {}).get("name"),
        "issue_status": fields.get("status", {}).get("name"),
        "assignee":    fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
        "reporter":    fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
        "created_at":  fields.get("created"),
        "updated_at":  fields.get("updated"),
        "labels":      fields.get("labels", [])
    }