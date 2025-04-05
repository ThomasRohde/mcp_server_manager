# Main application file for MCP Server Manager
# This will contain the FastAPI application

from fastapi import FastAPI, Request, Depends, HTTPException, status
from typing import List, Any, Dict
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.staticfiles import StaticFiles

from mcp_manager.core_logic import (
    read_installed_servers, 
    find_claude_processes, 
    terminate_processes, 
    start_claude_application,
    find_server_in_list,
    write_installed_servers,
    read_claude_config,
    update_claude_mcp_servers_section,
    write_claude_config,
    test_server_command
)

# Import the server discovery function
from mcp_manager.mcp_server import discover_servers_from_claude_config

app = FastAPI(title="MCP Server Manager", description="API for managing MCP servers")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")
# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    """
    Run tasks when the FastAPI application starts.
    """
    # Check for MCP servers in the Claude config and add them to our inventory
    discover_servers_from_claude_config()

@app.get("/")
async def get_root_page(request: Request):
    """
    Render the root page with the list of servers.
    """
    try:
        server_list = read_installed_servers()
        return templates.TemplateResponse("index.html", {"request": request, "servers": server_list})
    except Exception as e:
        # Handle errors
        raise HTTPException(
            status_code=500,
            detail=f"Failed to render page: {str(e)}"
        )

@app.get("/api/servers", response_model=List[Dict[str, Any]])
async def get_servers_api():
    """
    Get a list of all registered MCP servers.
    Returns an empty list if none are found or if there's an error reading the config.
    """
    try:
        servers = read_installed_servers()
        return servers
    except Exception as e:
        # Although read_installed_servers should handle errors internally,
        # catch any unexpected exceptions here for extra safety
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve servers: {str(e)}"
        )

@app.post("/api/claude/restart")
async def restart_claude_api():
    """
    Restart the Claude Desktop application by finding its process,
    terminating it, and starting it again. If Claude is not running,
    it will simply start Claude.
    """
    print("DEBUG: restart_claude_api endpoint called")
    
    # Find Claude processes
    print("DEBUG: Calling find_claude_processes()")
    processes = find_claude_processes()
    print(f"DEBUG: Found {len(processes)} Claude processes")
    
    # If no Claude processes found, just start Claude
    if not processes:
        print("DEBUG: No Claude processes found, proceeding to start Claude")
        
        # Start Claude application
        print("DEBUG: Calling start_claude_application()")
        success, error_msg = start_claude_application()
        print(f"DEBUG: start_claude_application result: success={success}, error_msg={error_msg}")
        
        if not success:
            print(f"DEBUG: Failed to start Claude Desktop: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start Claude Desktop: {error_msg}"
            )
        
        return {"status": "success", "message": "Claude Desktop started successfully."}
    
    # Terminate processes if found
    print("DEBUG: Calling terminate_processes()")
    success, error_msg = terminate_processes(processes)
    print(f"DEBUG: terminate_processes result: success={success}, error_msg={error_msg}")
    
    if not success:
        print(f"DEBUG: Failed to terminate Claude processes: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to terminate Claude processes: {error_msg}"
        )
    
    # Start Claude application
    print("DEBUG: Calling start_claude_application()")
    success, error_msg = start_claude_application()
    print(f"DEBUG: start_claude_application result: success={success}, error_msg={error_msg}")
    
    if not success:
        print(f"DEBUG: Failed to start Claude Desktop: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start Claude Desktop: {error_msg}"
        )
    
    print("DEBUG: Restart completed successfully")
    return {"status": "success", "message": "Claude Desktop restarted successfully."}

@app.put("/api/servers/{identifier}/status")
async def set_server_status_api(identifier: str, payload: Dict[str, bool]):
    """
    Enable or disable a server in both the installed_servers.json and claude_desktop_config.json files.
    
    Args:
        identifier: Server ID or name
        payload: Dictionary with {"enabled": true/false}
        
    Returns:
        Status message
    """
    # Validate payload
    enabled = payload.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must contain 'enabled' boolean field"
        )
    
    try:
        # Read installed servers
        servers = read_installed_servers()
        
        # Find the server by identifier
        server, error_msg = find_server_in_list(servers, identifier)
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg or f"Server '{identifier}' not found"
            )
        
        # Update the enabled_in_claude status in the server list
        server["enabled_in_claude"] = enabled
        write_installed_servers(servers)
        
        # Update Claude Desktop config
        claude_config = read_claude_config()
        
        # Prepare server details for Claude config
        if enabled:
            # Add/update server in Claude config
            server_details = {
                "command": server["command"][0],
                "args": server["command"][1:] + server["arguments"]
            }
            
            # Only include environment if non-empty
            if server.get("environment") and any(server["environment"].values()):
                server_details["env"] = server["environment"]
        else:
            # Remove from Claude config
            server_details = None
        
        # Update the Claude config
        claude_config = update_claude_mcp_servers_section(
            claude_config, 
            server["name"],
            server_details
        )
        write_claude_config(claude_config)
        
        status_text = "enabled" if enabled else "disabled"
        return {
            "status": "success",
            "message": f"Server '{server['name']}' {status_text}. Remember to restart Claude Desktop for changes to take effect."
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update server status: {str(e)}"
        )

# Run the application with: uvicorn main:app --reload
# Access the API docs at: http://127.0.0.1:8000/docs