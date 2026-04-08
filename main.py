import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from salesforce import create_lead, assign_permission_set, create_permission_set

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Salesforce MCP Server", version="1.0.0")


# -------------------------------
# ✅ ROOT (Uptime + Render warm)
# -------------------------------
@app.get("/")
def home():
    return JSONResponse(
        content={"status": "alive"},
        headers={"Cache-Control": "no-store"}
    )


@app.head("/")
def health_check():
    return JSONResponse(
        content={},
        headers={"Cache-Control": "no-store"}
    )


# -------------------------------
# 🔥 CRITICAL FIX (Agentforce needs this)
# -------------------------------
@app.head("/mcp")
async def mcp_head():
    return JSONResponse(
        content={},
        headers={"Cache-Control": "no-store"}
    )


@app.get("/mcp")
async def mcp_get():
    return JSONResponse(
        content={"status": "mcp alive"},
        headers={"Cache-Control": "no-store"}
    )


# -------------------------------
# MCP HANDLER
# -------------------------------
@app.post("/mcp")
async def mcp_handler(request: Request):
    try:
        body = await request.json()
        logger.info(f"Incoming MCP request: {body}")

        req_type = body.get("type")
        req_id = body.get("id")

        if not req_type or req_id is None:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "error",
                    "error": {"message": "Invalid body type"}
                },
                headers={"Cache-Control": "no-store"}
            )

        # -------------------------------
        # INITIALIZE
        # -------------------------------
        # -------------------------------
        if req_type == "initialize":
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {
                            "tools": {
                                "listChanged": False
                                }
                                },
                                "serverInfo": {
                                    "name": "salesforce-mcp-server",
                                    "version": "1.0.0"
                                    }
                                    }
                                    },
                                    headers={"Cache-Control": "no-store"}
                                    )

        # -------------------------------
        # TOOLS LIST
        # -------------------------------
        elif req_type == "tools/list":
            return JSONResponse(
                content={
                    "id": req_id,
                    "type": "result",
                    "result": {
                        "tools": [
                            {
                                "name": "createLead",
                                "description": "Create Salesforce Lead",
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
                                "name": "assignPermissionSet",
                                "description": "Assign permission set to user",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "permission_set_name": {"type": "string"}
                                    },
                                    "required": ["username", "permission_set_name"]
                                }
                            },
                            {
                                "name": "createPermissionSet",
                                "description": "Create Salesforce Permission Set",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "ps_name": {"type": "string"},
                                        "ps_label": {"type": "string"}
                                    },
                                    "required": ["ps_name", "ps_label"]
                                }
                            }
                        ]
                    }
                },
                headers={"Cache-Control": "no-store"}
            )

        # -------------------------------
        # TOOLS CALL
        # -------------------------------
        elif req_type == "tools/call":
            tool_name = body.get("name")
            args = body.get("arguments", {})

            try:
                if tool_name == "createLead":
                    result = create_lead(**args)
                elif tool_name == "assignPermissionSet":
                    result = assign_permission_set(**args)
                elif tool_name == "createPermissionSet":
                    result = create_permission_set(**args)
                else:
                    result = f"Unknown tool: {tool_name}"

                return JSONResponse(
                    content={
                        "id": req_id,
                        "type": "result",
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result
                                }
                            ]
                        }
                    },
                    headers={"Cache-Control": "no-store"}
                )

            except Exception as e:
                return JSONResponse(
                    content={
                        "id": req_id,
                        "type": "error",
                        "error": {"message": str(e)}
                    },
                    headers={"Cache-Control": "no-store"}
                )

        # -------------------------------
        # INVALID TYPE
        # -------------------------------
        else:
            return JSONResponse(
                content={
                    "id": req_id,
                    "type": "error",
                    "error": {"message": f"Invalid type: {req_type}"}
                },
                headers={"Cache-Control": "no-store"}
            )

    except Exception as e:
        logger.error(str(e))
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "error": {"message": str(e)}
            },
            headers={"Cache-Control": "no-store"}
        )