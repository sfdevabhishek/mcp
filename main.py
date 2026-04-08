import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from salesforce import create_lead, assign_permission_set, create_permission_set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Salesforce MCP Server", version="1.0.0")


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

        # Handle notifications (no id)
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
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "salesforce-mcp-server",
                        "version": "1.0.0"
                    }
                }
            })

        elif method == "ping":
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            })

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
                                    "label": {"type": "string"},
                                    "api_name": {"type": "string"},
                                    "description": {"type": "string"}
                                },
                                "required": ["label", "api_name"]
                            }
                        },
                        {
                            "name": "assignPermissionSet",
                            "description": "Assign a Permission Set to a Salesforce User",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string"},
                                    "permission_set_name": {"type": "string"}
                                },
                                "required": ["username", "permission_set_name"]
                            }
                        }
                    ]
                }
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            if tool_name == "createLead":
                result = create_lead(**args)
            elif tool_name == "createPermissionSet":
                result = create_permission_set(**args)
            elif tool_name == "assignPermissionSet":
                result = assign_permission_set(**args)
            else:
                result = f"Unknown tool: {tool_name}"

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(result)}]
                }
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