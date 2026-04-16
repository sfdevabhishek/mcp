import logging
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from salesforce import create_lead, assign_permission_set, create_permission_set, create_case, update_case_status
from neuron7 import get_messages
from jira import create_jira_issue
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
                            "name": "createLead",
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
                            "name": "createPermissionSet",
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
                            "name": "assignPermissionSet",
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
                            "name": "createCase",
                            "description": "Create a new support case in Salesforce",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "subject": {"type": "string", "description": "Short summary of the issue"},
                                    "description": {"type": "string", "description": "Detailed description of the issue"},
                                    "priority": {"type": "string", "description": "Priority: Low, Medium or High"},
                                    "origin": {"type": "string", "description": "Origin: Phone, Email or Web"}
                                },
                                "required": ["subject", "description", "priority", "origin", "jiraissueurl"]
                            }
                        },
                        {
                            "name": "attachjiraissuewithcase",
                            "description": "Attach the jira issue url with created case.",
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
                            "name": "getMessages",
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
    "name": "createJiraIssue",
    "description": "Create a new issue in Jira",
    "inputSchema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Short title of the Jira issue"},
            "description": {"type": "string", "description": "Detailed description of the issue"},
            "project_key": {"type": "string", "description": "Jira project key e.g. DEV, SUPPORT"},
            "issue_type": {"type": "string", "description": "Issue type: Task, Bug, Story (default: Task)"},
            "priority": {"type": "string", "description": "Priority: Lowest, Low, Medium, High, Highest (default: Medium)"},
            "assignee_email": {"type": "string", "description": "Email of the assignee (optional)"},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "List of labels (optional)"},
            "sf_case_id": {"type": "string", "description": "Salesforce Case ID to link (optional)"}
        },
        "required": ["summary", "description", "project_key"]
    }
}
                    ]  # ← tools list closes here
                }
            })  # ← JSONResponse closes here

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            if tool_name == "createLead":
                result = create_lead(**args)
            elif tool_name == "createPermissionSet":
                result = create_permission_set(**args)
            elif tool_name == "assignPermissionSet":
                result = assign_permission_set(**args)
            elif tool_name == "createCase":
                result = create_case(**args)
            elif tool_name == "updateCaseStatus":
                result = update_case_status(**args)
            elif tool_name == "getMessages":
                result = get_messages(**args)
            elif tool_name == "createJiraIssue":
                result = create_jira_issue(**args) 
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