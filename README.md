# Salesforce MCP Server

A FastAPI-based MCP (Model Context Protocol) server for Salesforce Agentforce Registry (Beta).

## Features

- **MCP Protocol Support**: Implements initialize, tools/list, and tools/call endpoints
- **Streamable HTTP**: Uses standard HTTP POST requests (not SSE)
- **Salesforce Integration**: Provides tools for lead management and permission sets
- **Production Ready**: Includes proper logging, error handling, and JSON responses

## Tools Available

1. **createLead**: Create a new Salesforce Lead
   - Parameters: `first_name`, `last_name`, `email`, `company`

2. **assignPermissionSet**: Assign a permission set to a user
   - Parameters: `username`, `permission_set_name`

3. **createPermissionSet**: Create a new permission set
   - Parameters: `ps_name`, `ps_label`

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env`:
   ```
   SALESFORCE_CLIENT_ID=your_client_id
   SALESFORCE_CLIENT_SECRET=your_client_secret
   SALESFORCE_USERNAME=your_username
   SALESFORCE_PASSWORD=your_password
   SALESFORCE_TOKEN_URL=https://login.salesforce.com/services/oauth2/token
   ```

3. Run the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## API Endpoints

- `GET /`: Health check
- `POST /mcp`: MCP protocol endpoint

## MCP Protocol

The server strictly follows the MCP protocol with JSON responses containing:
- `id`: Request ID
- `type`: Response type ("result" or "error")
- `result`: Response data for successful operations

## Logging

All incoming requests and operations are logged for debugging purposes.