"""
MCP Server module for MCP Server Manager.

This module provides an MCP interface for:
- Listing registered servers
- Installing/registering new MCP servers
- Setting server enabled status
- Restarting Claude Desktop
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Union

# Import MCP Server library
from mcp.server import Server
import mcp.types
import mcp.server.stdio
from mcp.server.models import InitializationOptions

# Import core logic functions
from mcp_manager.core_logic import (
    read_installed_servers,
    write_installed_servers,
    find_server_in_list,
    read_claude_config,
    update_claude_mcp_servers_section,
    write_claude_config,
    find_claude_processes,
    terminate_processes,
    start_claude_application,
    generate_unique_id
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the MCP server instance
server = Server("mcp-server-manager")


def discover_servers_from_claude_config() -> None:
    """
    Check the Claude Desktop config file for MCP servers not in our inventory,
    and add them to our installed_servers.json file.
    """
    logger.info("Discovering MCP servers from Claude Desktop config")
    
    try:
        # Read both configs
        installed_servers = read_installed_servers()
        claude_config = read_claude_config()
        
        # Extract server names from installed servers for easy lookup
        installed_server_names = {server.get('name', ''): server for server in installed_servers}
        
        # Check if the Claude config has an mcpServers section
        mcp_servers = claude_config.get('mcpServers', {})
        if not mcp_servers:
            logger.info("No MCP servers found in Claude Desktop config")
            return
        
        added_count = 0
        for server_name, server_config in mcp_servers.items():
            # Skip if server already exists in our inventory
            if server_name in installed_server_names:
                logger.info(f"Server '{server_name}' already in inventory, skipping")
                continue
                
            # Extract server details from Claude config
            command_str = server_config.get('command', '')
            args = server_config.get('args', [])
            env = server_config.get('env', {})
            
            if not command_str:
                logger.warning(f"Server '{server_name}' in Claude config has no command, skipping")
                continue
                
            # Create new server entry
            new_server = {
                'id': generate_unique_id(),
                'name': server_name,
                'command': [command_str],
                'arguments': args,
                'environment': env,
                'enabled_in_claude': True,
                'source_type': 'claude_config',
                'source_location': 'Discovered from Claude Desktop configuration'
            }
            
            # Add to installed servers
            installed_servers.append(new_server)
            added_count += 1
            logger.info(f"Added server '{server_name}' from Claude config to inventory")
        
        # Save updated inventory if changes were made
        if added_count > 0:
            write_installed_servers(installed_servers)
            logger.info(f"Added {added_count} servers from Claude config to inventory")
        else:
            logger.info("No new servers found in Claude config")
            
    except Exception as e:
        logger.error(f"Error discovering servers from Claude config: {str(e)}")


@server.list_resources()
async def handle_list_resources() -> List[mcp.types.Resource]:
    """
    Handler for listing available resources.
    
    Returns:
        List of Resource objects representing available resources
    """
    logger.info("Listing available resources")
    
    return [
        mcp.types.Resource(
            uri="mcpmanager://servers/installed",
            name="Installed MCP Servers",
            description="List of all MCP servers registered with this manager",
            mimeType="application/json"
        )
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """
    Handler for reading a resource.
    
    Args:
        uri: The URI of the resource to read
        
    Returns:
        The resource content as a string
        
    Raises:
        ValueError: If the requested URI is not recognized
    """
    logger.info(f"Reading resource: {uri}")
    
    if uri == "mcpmanager://servers/installed":
        try:
            servers = read_installed_servers()
            return json.dumps(servers, indent=2)
        except Exception as e:
            logger.error(f"Error reading installed servers: {str(e)}")
            raise
    else:
        logger.error(f"Unknown resource URI: {uri}")
        raise ValueError(f"Unknown resource URI: {uri}")


@server.list_tools()
async def handle_list_tools() -> List[mcp.types.Tool]:
    """
    Handler for listing available tools.
    
    Returns:
        List of Tool objects representing available tools
    """
    logger.info("Listing available tools")
    
    return [
        mcp.types.Tool(
            name="restart_claude_desktop",
            description="Finds, terminates, and restarts the Claude Desktop application",
            inputSchema={
                # No arguments needed for this tool
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        mcp.types.Tool(
            name="set_server_enabled_status",
            description="Enable or disable an MCP server in Claude Desktop. Requires either server_id OR server_name (not both), and an enabled flag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "The unique ID of the server to enable/disable"
                    },
                    "server_name": {
                        "type": "string",
                        "description": "The name of the server to enable/disable (use only if ID is unknown)"
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Whether to enable (true) or disable (false) the server"
                    }
                },
                "required": ["enabled"],
                "oneOf": [
                    {"required": ["server_id"]},
                    {"required": ["server_name"]}
                ]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[Union[mcp.types.TextContent, mcp.types.ImageContent, mcp.types.EmbeddedResource]]:
    """
    Handler for calling a tool.
    
    Args:
        name: The name of the tool to call
        arguments: The arguments to pass to the tool
        
    Returns:
        List of content objects representing the tool's response
        
    Raises:
        ValueError: If the requested tool is not recognized
    """
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    if name == "restart_claude_desktop":
        result = {}
        
        # Step 1: Find Claude processes
        logger.info("Finding Claude Desktop processes")
        processes = find_claude_processes()
        
        # If no processes found, we can skip to start
        if not processes:
            logger.info("No Claude Desktop processes found to terminate")
        else:
            # Step 2: Terminate processes
            logger.info(f"Terminating {len(processes)} Claude Desktop processes")
            success, error_msg = terminate_processes(processes)
            
            if not success:
                # Termination failed
                result = {
                    "status": "error",
                    "message": f"Failed to terminate Claude Desktop processes: {error_msg}"
                }
                logger.error(result["message"])
                return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            # Optional wait after termination
            logger.info("Waiting briefly before starting Claude Desktop")
            await asyncio.sleep(1)
        
        # Step 3: Start Claude application
        logger.info("Starting Claude Desktop application")
        success, error_msg = start_claude_application()
        
        if not success:
            # Start failed
            result = {
                "status": "error",
                "message": f"Failed to start Claude Desktop: {error_msg}"
            }
            logger.error(result["message"])
        else:
            # Success
            result = {
                "status": "success",
                "message": "Claude Desktop restarted successfully"
            }
            logger.info(result["message"])
        
        return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "set_server_enabled_status":
        # Extract and validate arguments
        enabled = arguments.get("enabled")
        server_id = arguments.get("server_id")
        server_name = arguments.get("server_name")
        
        # Validate that exactly one of server_id or server_name is provided
        if (server_id is None and server_name is None) or (server_id is not None and server_name is not None):
            error_msg = "You must provide exactly one of 'server_id' or 'server_name'"
            logger.error(error_msg)
            result = {
                "status": "error",
                "message": error_msg
            }
            return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        # Determine the identifier (either server_id or server_name)
        identifier = server_id if server_id is not None else server_name
        logger.info(f"Setting enabled status to {enabled} for server with {'ID' if server_id else 'name'}: {identifier}")
        
        try:
            # Step 1: Read installed servers
            servers = read_installed_servers()
            
            # Step 2: Find the server in the list
            found_server, error_msg = find_server_in_list(servers, identifier)
            
            if found_server is None:
                logger.error(error_msg)
                result = {
                    "status": "error",
                    "message": error_msg
                }
                return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            # Step 3: Update the server's enabled_in_claude field
            found_server['enabled_in_claude'] = enabled
            logger.info(f"Updated enabled status for server '{found_server['name']}' to {enabled}")
            
            # Step 4: Write updated servers list
            try:
                write_installed_servers(servers)
                logger.info("Successfully wrote updated servers list")
            except Exception as e:
                error_msg = f"Failed to write installed servers: {str(e)}"
                logger.error(error_msg)
                result = {
                    "status": "error",
                    "message": error_msg
                }
                return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            # Step 5: Read Claude config
            claude_config = read_claude_config()
            logger.info("Read Claude Desktop configuration file")
            
            # Step 6: Prepare server details for Claude config
            if enabled:
                # Create server details to add to Claude config
                server_details = {
                    "command": found_server['command'][0],
                    "args": found_server['command'][1:] + found_server['arguments']
                }
                # Only include environment if it's not empty
                if found_server.get('environment') and len(found_server['environment']) > 0:
                    server_details["env"] = found_server['environment']
            else:
                # Remove from Claude config by setting to None
                server_details = None
            
            # Step 7: Update Claude config
            updated_config = update_claude_mcp_servers_section(
                claude_config,
                found_server['name'],
                server_details
            )
            
            # Step 8: Write updated Claude config
            try:
                write_claude_config(updated_config)
                logger.info("Successfully wrote updated Claude configuration")
            except Exception as e:
                error_msg = f"Failed to write Claude configuration: {str(e)}"
                logger.error(error_msg)
                result = {
                    "status": "error",
                    "message": error_msg
                }
                return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            # Success
            message = f"Server '{found_server['name']}' {'enabled' if enabled else 'disabled'} in Claude Desktop. Remember to restart Claude for changes to take effect."
            result = {
                "status": "success",
                "message": message
            }
            logger.info(message)
            return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            error_msg = f"Unexpected error setting server status: {str(e)}"
            logger.exception(error_msg)
            result = {
                "status": "error",
                "message": error_msg
            }
            return [mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    else:
        logger.error(f"Unknown tool name: {name}")
        raise ValueError(f"Unknown tool name: {name}")
    

async def main_mcp():
    """
    Main function to initialize and run the MCP server.
    """
    logger.info("Starting MCP server manager...")
    
    # Discover servers from Claude config on startup
    discover_servers_from_claude_config()
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="MCP Server Manager",
                server_version="0.1.0",
                capabilities=server.get_capabilities(),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main_mcp())