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

def add_jira_comment(issue_key: str, comment: str) -> dict:
    auth = get_jira_auth()
    headers = {"Content-Type": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": comment
                        }
                    ]
                }
            ]
        }
    }

    response = requests.post(url, auth=auth, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return {
        "status":     "success",
        "comment_id": data.get("id"),
        "issue_key":  issue_key,
        "message":    f"Comment added to Jira issue {issue_key} successfully."
    }

def search_jira_issues(
    project_key: str = None,
    status: str = None,
    priority: str = None,
    assignee_email: str = None,
    keyword: str = None,
    max_results: int = 10
) -> dict:
    """
    Searches Jira issues using JQL (Jira Query Language).
    Builds the query dynamically based on provided filters.
    e.g. project, status, priority, assignee, keyword
    """
    auth = get_jira_auth()

    headers = {"Content-Type": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/search"

    # ── Build JQL dynamically based on provided filters ──────────────────────
    jql_parts = []

    if project_key:
        jql_parts.append(f"project = {project_key}")
    if status:
        jql_parts.append(f"status = \"{status}\"")
    if priority:
        jql_parts.append(f"priority = \"{priority}\"")
    if assignee_email:
        jql_parts.append(f"assignee = \"{assignee_email}\"")
    if keyword:
        jql_parts.append(f"summary ~ \"{keyword}\" OR description ~ \"{keyword}\"")

    # Default: return all issues ordered by created date if no filters
    jql = " AND ".join(jql_parts) if jql_parts else "ORDER BY created DESC"

    if jql_parts:
        jql += " ORDER BY created DESC"

    params = {
        "jql":        jql,
        "maxResults": max_results,
        "fields":     "summary,status,priority,assignee,issuetype,created,updated,labels"
    }

    response = requests.get(url, auth=auth, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()
    issues = data.get("issues", [])

    if not issues:
        return {
            "status":  "no_issues_found",
            "message": f"No Jira issues found for the given filters.",
            "issues":  []
        }

    # ── Format response ───────────────────────────────────────────────────────
    formatted_issues = [
        {
            "issue_key":  issue["key"],
            "issue_url":  f"{JIRA_BASE_URL}/browse/{issue['key']}",
            "summary":    issue["fields"].get("summary"),
            "status":     issue["fields"].get("status", {}).get("name"),
            "priority":   issue["fields"].get("priority", {}).get("name"),
            "issue_type": issue["fields"].get("issuetype", {}).get("name"),
            "assignee":   issue["fields"].get("assignee", {}).get("displayName") if issue["fields"].get("assignee") else None,
            "created_at": issue["fields"].get("created"),
            "updated_at": issue["fields"].get("updated"),
            "labels":     issue["fields"].get("labels", [])
        }
        for issue in issues
    ]

    return {
        "status":        "success",
        "total_found":   data.get("total"),
        "total_returned": len(formatted_issues),
        "jql_used":      jql,
        "issues":        formatted_issues
    }

def assign_jira_issue(issue_key: str, assignee_email: str) -> dict:
    """
    Assigns a Jira issue to a user by their email address.
    e.g. issue_key="KAN-42", assignee_email="john@acme.com"
    """
    auth = get_jira_auth()

    headers = {"Content-Type": "application/json"}

    # Step 1 — Get accountId from email address
    user_search_url = f"{JIRA_BASE_URL}/rest/api/3/user/search"
    user_response = requests.get(
        user_search_url,
        auth=auth,
        headers=headers,
        params={"query": assignee_email}
    )
    user_response.raise_for_status()

    users = user_response.json()

    if not users:
        return {
            "status":  "error",
            "message": f"No Jira user found with email '{assignee_email}'"
        }

    # Pick the first matched user
    account_id = users[0].get("accountId")
    display_name = users[0].get("displayName")

    # Step 2 — Assign the issue using accountId
    assign_url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/assignee"
    payload = {"accountId": account_id}

    response = requests.put(assign_url, auth=auth, headers=headers, json=payload)
    response.raise_for_status()

    return {
        "status":       "success",
        "issue_key":    issue_key,
        "issue_url":    f"{JIRA_BASE_URL}/browse/{issue_key}",
        "assigned_to":  display_name,
        "account_id":   account_id,
        "message":      f"Jira issue {issue_key} successfully assigned to {display_name}."
    }

def get_jira_users() -> dict:
    """
    Fetches all active and assignable Jira users.
    Call this FIRST before assignJiraIssue so the
    customer can select the correct user.
    """
    auth = get_jira_auth()

    headers = {"Content-Type": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/users/search"

    response = requests.get(url, auth=auth, headers=headers)
    response.raise_for_status()

    users = response.json()

    if not users:
        return {
            "status":  "no_users_found",
            "message": "No Jira users found.",
            "users":   []
        }

    # Filter out system/bot accounts — only return real users
    formatted_users = [
        {
            "account_id":   user.get("accountId"),
            "display_name": user.get("displayName"),
            "email":        user.get("emailAddress"),
            "account_type": user.get("accountType"),
            "active":       user.get("active")
        }
        for user in users
        if user.get("accountType") == "atlassian" and user.get("active") == True
    ]

    return {
        "status":         "success",
        "total_returned": len(formatted_users),
        "users":          formatted_users
    }

def update_jira_issue(
    issue_key: str,
    summary: str = None,
    description: str = None,
    priority: str = None,
    issue_type: str = None,
    labels: list = None
) -> dict:
    """
    Updates fields of an existing Jira issue.
    Only the provided fields will be updated — others remain unchanged.
    e.g. summary, description, priority, issue_type, labels
    """
    auth = get_jira_auth()

    headers = {"Content-Type": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"

    # ── Build payload dynamically — only include provided fields ─────────────
    fields = {}

    if summary:
        fields["summary"] = summary

    if description:
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": description
                        }
                    ]
                }
            ]
        }

    if priority:
        fields["priority"] = {"name": priority}

    if issue_type:
        fields["issuetype"] = {"name": issue_type}

    if labels:
        fields["labels"] = labels

    if not fields:
        return {
            "status":  "error",
            "message": "No fields provided to update. Please provide at least one field."
        }

    payload = {"fields": fields}

    response = requests.put(url, auth=auth, headers=headers, json=payload)
    response.raise_for_status()

    return {
        "status":        "success",
        "issue_key":     issue_key,
        "issue_url":     f"{JIRA_BASE_URL}/browse/{issue_key}",
        "updated_fields": list(fields.keys()),
        "message":       f"Jira issue {issue_key} updated successfully."
    }

def get_jira_comments(issue_key: str) -> dict:
    """
    Fetches all comments of an existing Jira issue.
    e.g. issue_key="KAN-42"
    """
    auth = get_jira_auth()

    headers = {"Content-Type": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment"

    response = requests.get(url, auth=auth, headers=headers)
    response.raise_for_status()

    data = response.json()
    comments = data.get("comments", [])

    if not comments:
        return {
            "status":  "no_comments_found",
            "message": f"No comments found for Jira issue {issue_key}.",
            "comments": []
        }

    formatted_comments = [
        {
            "comment_id": comment.get("id"),
            "author":     comment.get("author", {}).get("displayName"),
            "body":       " ".join(
                            text_node.get("text", "")
                            for block in comment.get("body", {}).get("content", [])
                            for text_node in block.get("content", [])
                            if text_node.get("type") == "text"
                          ),
            "created_at": comment.get("created"),
            "updated_at": comment.get("updated")
        }
        for comment in comments
    ]

    return {
        "status":         "success",
        "issue_key":      issue_key,
        "issue_url":      f"{JIRA_BASE_URL}/browse/{issue_key}",
        "total_comments": len(formatted_comments),
        "comments":       formatted_comments
    }


def get_jira_projects() -> dict:
    """
    Fetches all available Jira projects.
    Use this before createJiraIssue so the customer
    can select the correct project dynamically.
    """
    auth = get_jira_auth()

    headers = {"Content-Type": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/project"

    response = requests.get(url, auth=auth, headers=headers)
    response.raise_for_status()

    projects = response.json()

    if not projects:
        return {
            "status":   "no_projects_found",
            "message":  "No Jira projects found.",
            "projects": []
        }

    formatted_projects = [
        {
            "project_id":   project.get("id"),
            "project_key":  project.get("key"),
            "project_name": project.get("name"),
            "project_type": project.get("projectTypeKey"),
            "project_url":  f"{JIRA_BASE_URL}/browse/{project.get('key')}"
        }
        for project in projects
    ]

    return {
        "status":         "success",
        "total_returned": len(formatted_projects),
        "projects":       formatted_projects
    }