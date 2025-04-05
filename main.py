# Main application file for MCP Server Manager
# This will contain the FastAPI application

from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from typing import List, Any, Dict, Optional
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging

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
    test_server_command,
    generate_unique_id
)

# Import the server discovery function
from mcp_manager.mcp_server import discover_servers_from_claude_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    logger.info("Application startup: Discovering MCP servers from Claude config")
    discover_servers_from_claude_config()
    logger.info("Application startup complete")

@app.get("/")
async def get_root_page(request: Request):
    """
    Render the root page with the list of servers.
    
    Args:
        request: The FastAPI Request object
        
    Returns:
        TemplateResponse with the rendered index.html template
    
    Raises:
        HTTPException: If there's an error rendering the page
    """
    logger.info("GET / - Rendering root page")
    try:
        server_list = read_installed_servers()
        logger.info(f"Found {len(server_list)} servers to display")
        return templates.TemplateResponse("index.html", {"request": request, "servers": server_list})
    except Exception as e:
        # Handle errors
        logger.error(f"Failed to render root page: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to render page: {str(e)}"
        )

@app.get("/api/servers", response_model=List[Dict[str, Any]])
async def get_servers_api():
    """
    Get a list of all registered MCP servers.
    
    Returns:
        List of server dictionaries from the installed_servers.json file
        
    Raises:
        HTTPException: If there's an error retrieving the servers
    """
    logger.info("GET /api/servers - Retrieving server list")
    try:
        servers = read_installed_servers()
        logger.info(f"Successfully retrieved {len(servers)} servers")
        return servers
    except Exception as e:
        # Although read_installed_servers should handle errors internally,
        # catch any unexpected exceptions here for extra safety
        logger.exception(f"Failed to retrieve servers: {str(e)}")
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
    
    Returns:
        Dict with status and message
        
    Raises:
        HTTPException: If there's an error restarting Claude
    """
    logger.info("POST /api/claude/restart - Restarting Claude Desktop")
    
    # Find Claude processes
    logger.debug("Finding Claude Desktop processes")
    processes = find_claude_processes()
    logger.info(f"Found {len(processes)} Claude processes")
    
    # If no Claude processes found, just start Claude
    if not processes:
        logger.info("No Claude processes found, proceeding to start Claude")
        
        # Start Claude application
        logger.debug("Starting Claude Desktop application")
        success, error_msg = start_claude_application()
        logger.debug(f"Start Claude result: success={success}, error_msg={error_msg}")
        
        if not success:
            logger.error(f"Failed to start Claude Desktop: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start Claude Desktop: {error_msg}"
            )
        
        return {"status": "success", "message": "Claude Desktop started successfully."}
    
    # Terminate processes if found
    logger.debug("Terminating Claude Desktop processes")
    success, error_msg = terminate_processes(processes)
    logger.debug(f"Terminate processes result: success={success}, error_msg={error_msg}")
    
    if not success:
        logger.error(f"Failed to terminate Claude processes: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to terminate Claude processes: {error_msg}"
        )
    
    # Start Claude application
    logger.debug("Starting Claude Desktop application")
    success, error_msg = start_claude_application()
    logger.debug(f"Start Claude result: success={success}, error_msg={error_msg}")
    
    if not success:
        logger.error(f"Failed to start Claude Desktop: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start Claude Desktop: {error_msg}"
        )
    
    logger.info("Claude Desktop restarted successfully")
    return {"status": "success", "message": "Claude Desktop restarted successfully."}

@app.put("/api/servers/{identifier}/status")
async def set_server_status_api(identifier: str, payload: Dict[str, bool]):
    """
    Enable or disable a server in both the installed_servers.json and claude_desktop_config.json files.
    
    Args:
        identifier: Server ID or name
        payload: Dictionary with {"enabled": true/false}
        
    Returns:
        Dict with status and message
        
    Raises:
        HTTPException: If there's an error updating the server status
    """
    logger.info(f"PUT /api/servers/{identifier}/status - Updating server status")
    
    # Validate payload
    enabled = payload.get("enabled")
    if enabled is None or not isinstance(enabled, bool):
        logger.warning("Invalid payload: missing or non-boolean 'enabled' field")
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
            logger.warning(f"Server not found: {identifier}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg or f"Server '{identifier}' not found"
            )
        
        logger.info(f"Updating server '{server['name']}' (ID: {server['id']}) enabled status to: {enabled}")
        
        # Update the enabled_in_claude status in the server list
        server["enabled_in_claude"] = enabled
        write_installed_servers(servers)
        
        # Update Claude Desktop config
        logger.debug("Reading Claude Desktop configuration")
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
            
            logger.debug(f"Adding server '{server['name']}' to Claude config")
        else:
            # Remove from Claude config
            server_details = None
            logger.debug(f"Removing server '{server['name']}' from Claude config")
        
        # Update the Claude config
        claude_config = update_claude_mcp_servers_section(
            claude_config, 
            server["name"],
            server_details
        )
        write_claude_config(claude_config)
        
        status_text = "enabled" if enabled else "disabled"
        logger.info(f"Successfully {status_text} server '{server['name']}'")
        
        return {
            "status": "success",
            "message": f"Server '{server['name']}' {status_text}. Remember to restart Claude Desktop for changes to take effect."
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        logger.exception(f"Failed to update server status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update server status: {str(e)}"
        )

# Run the application with: uvicorn main:app --reload
# Access the API docs at: http://127.0.0.1:8000/docs

class ServerRegistrationForm(BaseModel):
    """Form data model for server registration."""
    name: str
    command_str: str
    arguments_str: str = ""
    environment_str: str = ""
    source_type: Optional[str] = None
    source_location: Optional[str] = None
    
    @classmethod
    def as_form(
        cls,
        name: str = Form(...),
        command_str: str = Form(...),
        arguments_str: str = Form(""),
        environment_str: str = Form(""),
        source_type: Optional[str] = Form(None),
        source_location: Optional[str] = Form(None),
    ):
        """
        Convert from form fields to Pydantic model.
        
        Args:
            name: Name of the server
            command_str: The command to run the server as a string
            arguments_str: Arguments to pass to the command as a string
            environment_str: Environment variables as a string (KEY=VALUE format, one per line)
            source_type: Type of source (e.g., local, git, pip)
            source_location: Source location (e.g., path, URL, package name)
            
        Returns:
            ServerRegistrationForm instance
        """
        return cls(
            name=name,
            command_str=command_str,
            arguments_str=arguments_str,
            environment_str=environment_str,
            source_type=source_type,
            source_location=source_location,
        )

@app.post("/api/servers")
async def register_server_api(form_data: ServerRegistrationForm = Depends(ServerRegistrationForm.as_form)):
    """
    Register a new MCP server.
    
    Processes the form data, verifies the server command, and adds it to installed_servers.json.
    
    Args:
        form_data: Form data with server details
        
    Returns:
        Dict with status and message
        
    Raises:
        HTTPException: If there's an error registering the server
    """
    logger.info(f"POST /api/servers - Registering new server: {form_data.name}")
    
    try:
        # Parse the command string into a list
        # Simple split by space for now (more sophisticated parsing could be added later)
        command_parts = form_data.command_str.strip().split()
        if not command_parts:
            logger.warning("Command string is empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Command cannot be empty"
            )
        
        # Parse arguments string into a list
        arguments = []
        if form_data.arguments_str.strip():
            arguments = form_data.arguments_str.strip().split()
        
        # Parse environment string into a dictionary
        environment = {}
        if form_data.environment_str.strip():
            for line in form_data.environment_str.strip().split("\n"):
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    environment[key.strip()] = value.strip()
        
        logger.info(f"Testing server command: {command_parts} with args {arguments}")
        # Test if the server command works
        success, error_msg = test_server_command(command_parts, arguments, environment)
        if not success:
            logger.warning(f"Server command verification failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server command verification failed: {error_msg}"
            )
        
        # Generate a unique ID for the server
        server_id = generate_unique_id()
        logger.debug(f"Generated server ID: {server_id}")
        
        # Create the server dictionary
        new_server = {
            "id": server_id,
            "name": form_data.name,
            "command": command_parts,
            "arguments": arguments,
            "environment": environment,
            "enabled_in_claude": False,  # Default to disabled
            "source_type": form_data.source_type,
            "source_location": form_data.source_location
        }
        
        # Read existing servers, append the new one, and write back
        servers = read_installed_servers()
        
        # Check for duplicate names
        for server in servers:
            if server['name'] == form_data.name:
                logger.warning(f"Duplicate server name: {form_data.name}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A server with the name '{form_data.name}' already exists"
                )
        
        servers.append(new_server)
        write_installed_servers(servers)
        
        logger.info(f"Successfully registered server '{form_data.name}' with ID: {server_id}")
        
        return {
            "status": "success",
            "message": f"Server '{form_data.name}' registered and verified successfully. Use the toggle to enable it in Claude Desktop.",
            "server_id": server_id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as they're already formatted correctly
        raise
        
    except Exception as e:
        # Handle unexpected errors
        logger.exception(f"Failed to register server: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register server: {str(e)}"
        )