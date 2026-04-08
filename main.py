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

        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params", {})

        if method is None or req_id is None:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request"
                    }
                }
            )

        # -------------------------
        # INITIALIZE
        # -------------------------

        if method == "initialize":

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
                }
            )

        # -------------------------
        # TOOLS LIST
        # -------------------------

        elif method == "tools/list":

            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
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
                                    "required": [
                                        "first_name",
                                        "last_name",
                                        "email",
                                        "company"
                                    ]
                                }
                            }
                        ]
                    }
                }
            )

        # -------------------------
        # TOOL CALL
        # -------------------------

        elif method == "tools/call":

            tool_name = params.get("name")
            args = params.get("arguments", {})

            if tool_name == "createLead":
                result = create_lead(**args)

            else:
                result = "Unknown tool"

            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                }
            )

        # -------------------------
        # UNKNOWN METHOD
        # -------------------------

        else:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": "Method not found"
                    }
                }
            )

    except Exception as e:
        logger.error(str(e))

        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        )