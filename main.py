import logging
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from salesforce import create_lead, assign_permission_set, create_permission_set, create_case, update_jiraurl, get_salesforce_users, update_case_status
from neuron7 import get_messages
from jira import create_jira_issue, update_jira_issue_status, get_jira_issue, add_jira_comment, search_jira_issues, assign_jira_issue, get_jira_users, update_jira_issue, get_jira_projects, get_jira_comments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def keep_alive():
    while True:
        await asyncio.sleep(300)
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://mcp-nj3p.onrender.com/")
            logger.info("✅ Keep-alive ping sent")
        except Exception as e:
            logger.warning(f"⚠️ Keep-alive failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(keep_alive())
    yield

app = FastAPI(title="Salesforce MCP Server", version="1.0.0", lifespan=lifespan)


@app.get("/")
def home():
    return JSONResponse(content={"status": "alive"}, headers={"Cache-Control": "no-store"})

@app.head("/")
def health_check():
    return JSONResponse(content={}, headers={"Cache-Control": "no-store"})

@app.head("/mcp")
async def mcp_head():
    return JSONResponse(content={}, headers={"Cache-Control": "no-store"})

@app.get("/mcp")
async def mcp_get():
    return JSONResponse(content={"status": "mcp alive"}, headers={"Cache-Control": "no-store"})


@app.post("/mcp")
async def mcp_handler(request: Request):
    try:
        body = await request.json()
        logger.info(f"Incoming MCP request: {body}")

        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params", {})

        if req_id is None:
            logger.info(f"Received notification: {method} — ignoring")
            return Response(status_code=204)

        if method is None:
            return JSONResponse(
                status_code=400,
                content={"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
            )

        if method == "initialize":
            client_version = params.get("protocolVersion", "2024-11-05")
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": client_version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "salesforce-mcp-server", "version": "1.0.0"}
                }
            })

        elif method == "ping":
            return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": {}})

        elif method == "tools/list":
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        # ── SALESFORCE TOOLS ──────────────────────────────────────────
                        {
                            "name": "Create Lead",
                            "description": "Create a new Lead in Salesforce",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "first_name": {"type": "string"},
                                    "last_name":  {"type": "string"},
                                    "email":      {"type": "string"},
                                    "company":    {"type": "string"}
                                },
                                "required": ["first_name", "last_name", "email", "company"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":  {"type": "string", "description": "success or error"},
                                    "lead_id": {"type": "string", "description": "Salesforce Lead ID"},
                                    "message": {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Create Permission Set",
                            "description": "Create a new Permission Set in Salesforce",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "api_name": {"type": "string", "description": "API name (no spaces)"},
                                    "label":    {"type": "string", "description": "Display label"}
                                },
                                "required": ["api_name", "label"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":            {"type": "string", "description": "success or error"},
                                    "permission_set_id": {"type": "string", "description": "Salesforce Permission Set ID"},
                                    "message":           {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Assign Permission Set",
                            "description": "Assign a Permission Set to a Salesforce User",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "username":            {"type": "string", "description": "Salesforce username (email format)"},
                                    "permission_set_name": {"type": "string", "description": "API name of the permission set"}
                                },
                                "required": ["username", "permission_set_name"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":        {"type": "string", "description": "success or error"},
                                    "assignment_id": {"type": "string", "description": "Permission Set Assignment ID"},
                                    "message":       {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Create Case",
                            "description": "Create a new support case in Salesforce",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "subject":     {"type": "string", "description": "Short summary of the issue"},
                                    "description": {"type": "string", "description": "Detailed description of the issue"},
                                    "priority":    {"type": "string", "description": "Priority: Low, Medium or High"},
                                    "origin":      {"type": "string", "description": "Origin: Phone, Email or Web"}
                                },
                                "required": ["subject", "description", "priority", "origin"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":   {"type": "string", "description": "success or error"},
                                    "case_id":  {"type": "string", "description": "Salesforce Case ID"},
                                    "case_url": {"type": "string", "description": "URL to the Salesforce Case record"},
                                    "message":  {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Attach jira issue with case",
                            "description": "Attach the jira issue url with created case. Always call this tool Immediately after creating the jira issue",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "case_id":      {"type": "string", "description": "Salesforce Case ID"},
                                    "jiraissueurl": {"type": "string", "description": "Url of the created jira issue"}
                                },
                                "required": ["case_id", "jiraissueurl"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":  {"type": "string", "description": "success or error"},
                                    "case_id": {"type": "string", "description": "Salesforce Case ID updated"},
                                    "message": {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Get Salesforce Users",
                            "description": "Retrieve all active Salesforce users. Always call this tool FIRST before assigning a permission set so the customer can select the correct user.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string",  "description": "success or error"},
                                    "total":  {"type": "integer", "description": "Total number of users returned"},
                                    "users": {
                                        "type": "array",
                                        "description": "List of active Salesforce users",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id":       {"type": "string", "description": "Salesforce User ID"},
                                                "name":     {"type": "string", "description": "Full name"},
                                                "email":    {"type": "string", "description": "Email address"},
                                                "username": {"type": "string", "description": "Salesforce username"}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "name": "Update Case Status",
                            "description": "Update the status of an existing Salesforce Case. Use this to close or update a case when an incident is resolved.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "case_id": {"type": "string", "description": "Salesforce Case ID e.g. 5001X000ABC"},
                                    "status":  {"type": "string", "description": "New status: New, Working, Escalated, Closed"}
                                },
                                "required": ["case_id", "status"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":  {"type": "string", "description": "success or error"},
                                    "case_id": {"type": "string", "description": "Salesforce Case ID updated"},
                                    "message": {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        # ---------Neuron Tools-----
                        {
                            "name": "Provide Solutions",
                            "description": "Send a query and get a bot response from N7 messaging service",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "The message or question to send to the bot"}
                                },
                                "required": ["query"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "message":  {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        # ── JIRA TOOLS ────────────────────────────────────────────────
                        {
                            "name": "Create Jira Issue",
                            "description": "Create jira issues. Always call this tool Immediately after creating the salesforce case record",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "summary":     {"type": "string", "description": "Short title of the Jira issue"},
                                    "description": {"type": "string", "description": "Detailed description of the issue"},
                                    "sf_case_id":  {"type": "string", "description": "Salesforce Case ID to link"}
                                },
                                "required": ["summary", "description", "sf_case_id"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":    {"type": "string", "description": "success or error"},
                                    "issue_key": {"type": "string", "description": "Jira Issue Key e.g. KAN-42"},
                                    "issue_url": {"type": "string", "description": "URL to the Jira issue"},
                                    "message":   {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Update Jira Issue Status",
                            "description": "Update the status of an existing Jira issue. Use this to transition a Jira ticket to In Progress, In Review, Done, or To Do.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "issue_key": {"type": "string", "description": "Jira issue key e.g. KAN-42"},
                                    "status":    {"type": "string", "description": "Target status: To Do, In Progress, In Review, Done"}
                                },
                                "required": ["issue_key", "status"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":    {"type": "string", "description": "success or error"},
                                    "issue_key": {"type": "string", "description": "Jira Issue Key"},
                                    "message":   {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Get Jira Issue Details",
                            "description": "Fetch the details of an existing Jira issue by its key. Use this to check the current status, assignee, priority, and description of a Jira ticket.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "issue_key": {"type": "string", "description": "Jira issue key e.g. KAN-42"}
                                },
                                "required": ["issue_key"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":       {"type": "string", "description": "success or error"},
                                    "issue_key":    {"type": "string", "description": "Jira Issue Key"},
                                    "issue_url":    {"type": "string", "description": "URL to the Jira issue"},
                                    "summary":      {"type": "string", "description": "Issue summary/title"},
                                    "issue_status": {"type": "string", "description": "Current status of the issue"},
                                    "priority":     {"type": "string", "description": "Issue priority"},
                                    "issue_type":   {"type": "string", "description": "Issue type e.g. Bug, Task"},
                                    "assignee":     {"type": "string", "description": "Assigned user display name"},
                                    "reporter":     {"type": "string", "description": "Reporter display name"},
                                    "created_at":   {"type": "string", "description": "Issue creation timestamp"},
                                    "updated_at":   {"type": "string", "description": "Last updated timestamp"}
                                }
                            }
                        },
                        {
                            "name": "Add Jira Comment",
                            "description": "Add a comment to an existing Jira issue. Use this to post updates, progress notes, or resolution details directly on a Jira ticket.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "issue_key": {"type": "string", "description": "Jira issue key e.g. KAN-42"},
                                    "comment":   {"type": "string", "description": "The comment text to post on the Jira issue"}
                                },
                                "required": ["issue_key", "comment"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":     {"type": "string", "description": "success or error"},
                                    "comment_id": {"type": "string", "description": "ID of the created comment"},
                                    "issue_key":  {"type": "string", "description": "Jira Issue Key"},
                                    "message":    {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Retrieve Jira Issues",
                            "description": "Search for Jira issues using filters like project, status, priority, assignee, or keyword. Use this to find existing tickets before creating new ones or to get an overview of open issues.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "project_key":    {"type": "string",  "description": "Jira project key e.g. KAN"},
                                    "status":         {"type": "string",  "description": "Issue status: To Do, In Progress, In Review, Done"},
                                    "priority":       {"type": "string",  "description": "Priority: Low, Medium, High, Critical"},
                                    "assignee_email": {"type": "string",  "description": "Email of the assignee e.g. john@acme.com"},
                                    "keyword":        {"type": "string",  "description": "Search keyword in summary or description"},
                                    "max_results":    {"type": "integer", "description": "Maximum number of results to return (default: 10)"}
                                },
                                "required": []
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":          {"type": "string",  "description": "success or error"},
                                    "total_found":     {"type": "integer", "description": "Total issues matching the query"},
                                    "total_returned":  {"type": "integer", "description": "Number of issues returned"},
                                    "jql_used":        {"type": "string",  "description": "JQL query that was executed"},
                                    "issues": {
                                        "type": "array",
                                        "description": "List of matching Jira issues",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "issue_key":  {"type": "string", "description": "Jira Issue Key"},
                                                "issue_url":  {"type": "string", "description": "URL to the Jira issue"},
                                                "summary":    {"type": "string", "description": "Issue summary"},
                                                "status":     {"type": "string", "description": "Current status"},
                                                "priority":   {"type": "string", "description": "Issue priority"},
                                                "assignee":   {"type": "string", "description": "Assigned user"}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "name": "Assign Jira Issue",
                            "description": "Assign an existing Jira issue to a user by their email address. Use this after Retrieve Jira Users to assign the right ticket to the right engineer.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "issue_key":      {"type": "string", "description": "Jira issue key e.g. KAN-42"},
                                    "assignee_email": {"type": "string", "description": "Email of the user to assign e.g. john@acme.com"}
                                },
                                "required": ["issue_key", "assignee_email"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":      {"type": "string", "description": "success or error"},
                                    "issue_key":   {"type": "string", "description": "Jira Issue Key"},
                                    "issue_url":   {"type": "string", "description": "URL to the Jira issue"},
                                    "assigned_to": {"type": "string", "description": "Display name of the assigned user"},
                                    "message":     {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Retrieve Jira Users",
                            "description": "Retrieve all active Jira users. Always call this tool FIRST before assigning a Jira issue so the customer can select the correct user to assign.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":         {"type": "string",  "description": "success or error"},
                                    "total_returned": {"type": "integer", "description": "Total number of users returned"},
                                    "users": {
                                        "type": "array",
                                        "description": "List of active Jira users",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "account_id":   {"type": "string",  "description": "Jira Account ID"},
                                                "display_name": {"type": "string",  "description": "Full name of the user"},
                                                "email":        {"type": "string",  "description": "Email address"},
                                                "active":       {"type": "boolean", "description": "Whether the user is active"}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "name": "Update Jira Issue",
                            "description": "Update fields of an existing Jira issue such as summary, description, priority, issue type, or labels. Only the provided fields will be updated — others remain unchanged.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "issue_key":   {"type": "string", "description": "Jira issue key e.g. KAN-42"},
                                    "summary":     {"type": "string", "description": "New summary/title for the issue"},
                                    "description": {"type": "string", "description": "New description for the issue"},
                                    "priority":    {"type": "string", "description": "New priority: Low, Medium, High, Critical"},
                                    "issue_type":  {"type": "string", "description": "New issue type: Bug, Task, Story, Epic"},
                                    "labels":      {"type": "array",  "items": {"type": "string"}, "description": "New labels list"}
                                },
                                "required": ["issue_key"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":         {"type": "string", "description": "success or error"},
                                    "issue_key":      {"type": "string", "description": "Jira Issue Key"},
                                    "issue_url":      {"type": "string", "description": "URL to the Jira issue"},
                                    "updated_fields": {"type": "array", "items": {"type": "string"}, "description": "List of fields that were updated"},
                                    "message":        {"type": "string", "description": "Result message"}
                                }
                            }
                        },
                        {
                            "name": "Retrieve Jira Comments",
                            "description": "Fetch all comments of an existing Jira issue. Use this to read the latest updates, progress notes, or resolution details posted on a Jira ticket.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "issue_key": {"type": "string", "description": "Jira issue key e.g. KAN-42"}
                                },
                                "required": ["issue_key"]
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":         {"type": "string",  "description": "success or error"},
                                    "issue_key":      {"type": "string",  "description": "Jira Issue Key"},
                                    "issue_url":      {"type": "string",  "description": "URL to the Jira issue"},
                                    "total_comments": {"type": "integer", "description": "Total number of comments"},
                                    "comments": {
                                        "type": "array",
                                        "description": "List of comments on the issue",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "comment_id": {"type": "string", "description": "Comment ID"},
                                                "author":     {"type": "string", "description": "Author display name"},
                                                "body":       {"type": "string", "description": "Comment text content"},
                                                "created_at": {"type": "string", "description": "Comment creation timestamp"}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "name": "Provide Jira Projects",
                            "description": "Retrieve all available Jira projects. Always call this tool FIRST before creating a Jira issue so the customer can select the correct project dynamically instead of hardcoding a project key.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "status":         {"type": "string",  "description": "success or error"},
                                    "total_returned": {"type": "integer", "description": "Total number of projects returned"},
                                    "projects": {
                                        "type": "array",
                                        "description": "List of available Jira projects",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "project_id":   {"type": "string", "description": "Jira Project ID"},
                                                "project_key":  {"type": "string", "description": "Jira Project Key e.g. KAN"},
                                                "project_name": {"type": "string", "description": "Full project name"},
                                                "project_type": {"type": "string", "description": "Project type e.g. software, service_desk"},
                                                "project_url":  {"type": "string", "description": "URL to the Jira project"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    ]  # ← tools list closes here
                }
            })  # ← JSONResponse closes here

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            if tool_name == "Create Lead":
                result = create_lead(**args)
            elif tool_name == "Create Permission Set":
                result = create_permission_set(**args)
            elif tool_name == "Assign Permission Set":
                result = assign_permission_set(**args)
            elif tool_name == "Create Case":
                result = create_case(**args)
            elif tool_name == "Attach jira issue with case":
                result = update_jiraurl(**args)
            elif tool_name == "Provide Solutions":
                result = get_messages(**args)
            elif tool_name == "Create Jira Issue":
                result = create_jira_issue(**args)
            elif tool_name == "Get Salesforce Users":
                result = get_salesforce_users()
            elif tool_name == "Update Jira Issue Status":
                result = update_jira_issue_status(**args)
            elif tool_name == "Get Jira Issue Details":
                result = get_jira_issue(**args)
            elif tool_name == "Update Case Status":
                result = update_case_status(**args)
            elif tool_name == "Add Jira Comment":
                result = add_jira_comment(**args)
            elif tool_name == "Retrieve Jira Issues":
                result = search_jira_issues(**args)
            elif tool_name == "Assign Jira Issue":
                result = assign_jira_issue(**args)
            elif tool_name == "Retrieve Jira Users":
                result = get_jira_users()
            elif tool_name == "Update Jira Issue":
                result = update_jira_issue(**args)
            elif tool_name == "Retrieve Jira Comments":
                result = get_jira_comments(**args)
            elif tool_name == "Provide Jira Projects":
                result = get_jira_projects()
            else:
                result = f"Unknown tool: {tool_name}"

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": str(result)}]}
            })

        else:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            })

    except Exception as e:
        logger.error(str(e))
        return JSONResponse(
            status_code=500,
            content={"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
        )