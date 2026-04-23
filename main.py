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


# ✅ Keep-alive ping every 5 minutes
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
                        {
                            "name": "Create Lead",
                            "description": "Create a new Lead in Salesforce",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "first_name": {"type": "string"},
                                    "last_name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "company": {"type": "string"}
                                },
                                "required": ["first_name", "last_name", "email", "company"]
                            }
                        },
                        {
                            "name": "Create Permission Set",
                            "description": "Create a new Permission Set in Salesforce",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "api_name": {"type": "string", "description": "API name (no spaces)"},
                                    "label": {"type": "string", "description": "Display label"}
                                },
                                "required": ["api_name", "label"]
                            }
                        },
                        {
                            "name": "Assign Permission Set",
                            "description": "Assign a Permission Set to a Salesforce User",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string", "description": "Salesforce username (email format)"},
                                    "permission_set_name": {"type": "string", "description": "API name of the permission set"}
                                },
                                "required": ["username", "permission_set_name"]
                            }
                        },
                        {
                            "name": "Create Case",
                            "description": "Create a new support case in Salesforce",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "subject": {"type": "string", "description": "Short summary of the issue"},
                                    "description": {"type": "string", "description": "Detailed description of the issue"},
                                    "priority": {"type": "string", "description": "Priority: Low, Medium or High"},
                                    "origin": {"type": "string", "description": "Origin: Phone, Email or Web"}
                                },
                                "required": ["subject", "description", "priority", "origin"]
                            }
                        },
                        {
                            "name": "Attach jira issue with case",
                            "description": "Attach the jira issue url with created case. Always call this tool Immediately after creating the jira issue",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "case_id": {"type": "string", "description": "Salesforce Case ID"},
                                    "jiraissueurl": {"type": "string", "description": "Url of the created jira issue"}

                                },
                                "required": ["case_id", "jiraissueurl"]
                            }
                        },
                        {
                            "name": "Provide Solutions",
                            "description": "Send a query and get a bot response from N7 messaging service",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "The message or question to send to the bot"}
                                },
                                "required": ["query"]
                            }
                        },
                        {
    "name": "Create Jira Issue",
    "description": "Create jira issues. Always call this tool Immediately after creating the salesforce case record",
    "inputSchema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Short title of the Jira issue"},
            "description": {"type": "string", "description": "Detailed description of the issue"},
            "sf_case_id": {"type": "string", "description": "Salesforce Case ID to link (optional)"}
        },
        "required": ["summary", "description","sf_case_id" ]
    }
},
{
    "name": "Get Salesforce Users",
    "description": "Retrieve all active Salesforce users. Always call this tool FIRST before assigning a permission set so the customer can select the correct user.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": []
    }
},
{
    "name": "Update Jira Issue Status",
    "description": "Update the status of an existing Jira issue. Use this to transition a Jira ticket to In Progress, In Review, Done, or To Do.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "issue_key": {"type": "string", "description": "Jira issue key e.g. ENG-101"},
            "status": {"type": "string", "description": "Target status: To Do, In Progress, In Review, Done"}
        },
        "required": ["issue_key", "status"]
    }
},
{
    "name": "Get Jira Issue Details",
    "description": "Fetch the details of an existing Jira issue by its key. Use this to check the current status, assignee, priority, and description of a Jira ticket.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "issue_key": {"type": "string", "description": "Jira issue key e.g. ENG-101"}
        },
        "required": ["issue_key"]
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
    }
},
{
    "name": "Retrieve Jira Issues",
    "description": "Search for Jira issues using filters like project, status, priority, assignee, or keyword. Use this to find existing tickets before creating new ones or to get an overview of open issues.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_key":     {"type": "string", "description": "Jira project key e.g. KAN"},
            "status":          {"type": "string", "description": "Issue status: To Do, In Progress, In Review, Done"},
            "priority":        {"type": "string", "description": "Priority: Low, Medium, High, Critical"},
            "assignee_email":  {"type": "string", "description": "Email of the assignee e.g. john@acme.com"},
            "keyword":         {"type": "string", "description": "Search keyword in summary or description"},
            "max_results":     {"type": "integer", "description": "Maximum number of results to return (default: 10)"}
        },
        "required": []
    }
},
{
    "name": "Assign Jira Issue",
    "description": "Assign an existing Jira issue to a user by their email address. Use this after searchJiraIssues to assign the right ticket to the right engineer.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "issue_key":       {"type": "string", "description": "Jira issue key e.g. KAN-42"},
            "assignee_email":  {"type": "string", "description": "Email of the user to assign e.g. john@acme.com"}
        },
        "required": ["issue_key", "assignee_email"]
    }
},
{
    "name": "Retrieve Jira Users",
    "description": "Retrieve all active Jira users. Always call this tool FIRST before assigning a Jira issue so the customer can select the correct user to assign.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": []
    }
},
{
    "name": "Update Jira Issue",
    "description": "Update fields of an existing Jira issue such as summary, description, priority, issue type, or labels. Only the provided fields will be updated — others remain unchanged.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "issue_key":   {"type": "string",  "description": "Jira issue key e.g. KAN-42"},
            "summary":     {"type": "string",  "description": "New summary/title for the issue"},
            "description": {"type": "string",  "description": "New description for the issue"},
            "priority":    {"type": "string",  "description": "New priority: Low, Medium, High, Critical"},
            "issue_type":  {"type": "string",  "description": "New issue type: Bug, Task, Story, Epic"},
            "labels":      {"type": "array",   "items": {"type": "string"}, "description": "New labels list e.g. ['incident', 'agentforce']"}
        },
        "required": ["issue_key"]
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
    }
},
{
    "name": "Provide Jira Projects",
    "description": "Retrieve all available Jira projects. Always call this tool FIRST before creating a Jira issue so the customer can select the correct project dynamically instead of hardcoding a project key.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": []
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
                result = get_salesforce_users(**args)
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
                result = get_jira_users(**args)
            elif tool_name == "Update Jira Issue":
                result = get_jira_comments(**args)
            elif tool_name == "Retrieve Jira Comments":
                result = (**args)
            elif tool_name == "Provide Jira Projects":
                result = get_jira_projects(**args)  
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