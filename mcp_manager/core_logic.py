"""
Core logic for the MCP Server Manager.

This module contains shared functions independent of MCP/FastAPI:
- Configuration path resolution
- Reading/writing/parsing installed_servers.json
- Reading/writing/parsing/modifying claude_desktop_config.json
- Finding registered servers
- Generating unique IDs
- Testing server commands
- Managing Claude Desktop processes
- Error handling and logging
"""

import os
import pathlib
import json
import logging
import subprocess
import sys
import uuid
import platformdirs
import psutil
import shutil
from typing import Dict, List, Optional, Tuple, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Application constants
APP_NAME = "MCPManager"
INSTALLED_SERVERS_FILENAME = "installed_servers.json"
CLAUDE_CONFIG_FILENAME = "claude_desktop_config.json"


def get_config_path(filename: str) -> pathlib.Path:
    """
    Get the full path to a configuration file in the application data directory.
    
    Args:
        filename: Name of the configuration file
        
    Returns:
        Path object representing the full path to the file
    """
    base_dir = platformdirs.user_data_dir(APP_NAME)
    os.makedirs(base_dir, exist_ok=True)
    return pathlib.Path(base_dir) / filename


def get_claude_config_path() -> pathlib.Path:
    """
    Get the path to the Claude Desktop configuration file based on the operating system.
    
    Returns:
        Path object representing the full path to the Claude config file
    
    Raises:
        ValueError: If the operating system is not supported or required environment variables are missing
    """
    if sys.platform == "darwin":  # macOS
        return pathlib.Path.home() / "Library" / "Application Support" / "Claude" / CLAUDE_CONFIG_FILENAME
    elif sys.platform == "win32":  # Windows
        appdata = os.getenv("APPDATA")
        if not appdata:
            logger.error("APPDATA environment variable not set")
            raise ValueError("APPDATA environment variable not set")
        return pathlib.Path(appdata) / "Claude" / CLAUDE_CONFIG_FILENAME
    elif sys.platform == "linux":  # Linux
        # Try standard location first
        standard_path = pathlib.Path.home() / ".config" / "Claude" / CLAUDE_CONFIG_FILENAME
        # Could also check Flatpak location if standard path doesn't exist
        # flatpak_path = pathlib.Path.home() / ".var" / "app" / "com.anthropic.Claude" / "config" / "Claude" / CLAUDE_CONFIG_FILENAME
        return standard_path
    else:
        logger.error(f"Unsupported platform: {sys.platform}")
        raise ValueError(f"Unsupported platform: {sys.platform}")


def read_installed_servers() -> List[Dict[str, Any]]:
    """
    Read and parse the installed_servers.json file.
    
    Returns:
        List of dictionaries, each representing a registered server
    """
    file_path = get_config_path(INSTALLED_SERVERS_FILENAME)
    
    try:
        if not file_path.exists():
            logger.info(f"Servers config file does not exist at {file_path}")
            return []
        
        with open(file_path, 'r') as f:
            content = f.read()
            
        if not content.strip():
            logger.info(f"Servers config file is empty at {file_path}")
            return []
            
        servers = json.loads(content)
        logger.info(f"Successfully read {len(servers)} servers from configuration")
        return servers
    
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON in servers config file: {str(e)}")
        return []
    
    except IOError as e:
        logger.error(f"IO error reading servers config file: {str(e)}")
        return []


def write_installed_servers(servers: List[Dict[str, Any]]) -> None:
    """
    Write the server list to the installed_servers.json file.
    
    Args:
        servers: List of dictionaries, each representing a registered server
    """
    file_path = get_config_path(INSTALLED_SERVERS_FILENAME)
    
    # Ensure the directory exists
    os.makedirs(file_path.parent, exist_ok=True)
    
    try:
        with open(file_path, 'w') as f:
            json.dump(servers, f, indent=2)
        logger.info(f"Successfully wrote {len(servers)} servers to configuration")
    
    except IOError as e:
        logger.error(f"IO error writing servers config file: {str(e)}")
        raise


def generate_unique_id() -> str:
    """
    Generate a unique ID for a new server registration.
    
    Returns:
        A unique string identifier
    """
    return str(uuid.uuid4())


def find_server_in_list(servers: List[Dict[str, Any]], identifier: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Find a server in the list by its ID or name.
    
    Args:
        servers: List of server dictionaries
        identifier: Server ID or name to search for
        
    Returns:
        Tuple (server_dict, error_message)
        - If found, (server_dict, None)
        - If not found, (None, error_message)
        - If ambiguous (multiple by same name), (None, error_message)
    """
    # First, check for a server with matching ID
    for server in servers:
        if server.get('id') == identifier:
            logger.info(f"Found server with ID '{identifier}'")
            return (server, None)
    
    # If no ID match, look for servers with matching name
    name_matches = [server for server in servers if server.get('name') == identifier]
    
    if len(name_matches) == 1:
        # Exactly one name match found
        logger.info(f"Found server with name '{identifier}'")
        return (name_matches[0], None)
    elif len(name_matches) == 0:
        # No matches found
        error_msg = f"No server found with identifier '{identifier}'."
        logger.warning(error_msg)
        return (None, error_msg)
    else:
        # Multiple matches found - ambiguous
        error_msg = f"Multiple servers found with name '{identifier}'. Use unique ID."
        logger.warning(error_msg)
        return (None, error_msg)


def read_claude_config() -> Dict[str, Any]:
    """
    Read and parse the Claude Desktop configuration file.
    
    Returns:
        Dictionary containing Claude Desktop configuration.
        Returns an empty dictionary if file doesn't exist or has errors.
    """
    try:
        file_path = get_claude_config_path()
        
        if not file_path.exists():
            logger.info(f"Claude config file does not exist at {file_path}")
            return {}
        
        with open(file_path, 'r') as f:
            content = f.read()
            
        if not content.strip():
            logger.info(f"Claude config file is empty at {file_path}")
            return {}
            
        config = json.loads(content)
        logger.info(f"Successfully read Claude configuration")
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON in Claude config file: {str(e)}")
        return {}
    
    except IOError as e:
        logger.error(f"IO error reading Claude config file: {str(e)}")
        return {}


def write_claude_config(config: Dict[str, Any]) -> None:
    """
    Write configuration to the Claude Desktop configuration file.
    
    Args:
        config: Dictionary containing the complete Claude Desktop configuration
    """
    file_path = get_claude_config_path()
    
    # Ensure the directory exists
    os.makedirs(file_path.parent, exist_ok=True)
    
    try:
        with open(file_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Successfully wrote Claude configuration to {file_path}")
    
    except IOError as e:
        logger.error(f"IO error writing Claude config file: {str(e)}")
        raise


def update_claude_mcp_servers_section(
    config: Dict[str, Any], 
    server_name: str, 
    server_details: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Update the mcpServers section of the Claude Desktop configuration.
    
    Args:
        config: The Claude Desktop configuration dictionary
        server_name: Name of the server to add, update, or remove
        server_details: Dictionary with server details or None to remove the server
        
    Returns:
        Updated configuration dictionary
    """
    # Ensure the mcpServers section exists
    if 'mcpServers' not in config:
        logger.info("Creating new mcpServers section in Claude config")
        config['mcpServers'] = {}
    
    if server_details is None:
        # Remove server from config if it exists
        if server_name in config['mcpServers']:
            logger.info(f"Removing server '{server_name}' from Claude config")
            config['mcpServers'].pop(server_name, None)
    else:
        # Add or update server in config
        logger.info(f"Adding/updating server '{server_name}' in Claude config")
        config['mcpServers'][server_name] = server_details
    
    return config


def test_server_command(
    command: List[str], 
    args: List[str], 
    env: Optional[Dict[str, str]]
) -> Tuple[bool, Optional[str]]:
    """
    Test if a server command can be launched successfully.
    
    This function attempts to launch a command with the specified arguments
    and environment variables. It briefly starts the process and checks if
    it launches without immediately crashing. The process is terminated
    after a short test period.
    
    Args:
        command: List of command components (e.g., ["python", "-m", "server"])
        args: List of arguments to pass to the command
        env: Optional dictionary of environment variables
        
    Returns:
        Tuple (success, error_message)
        - If success, (True, None)
        - If error, (False, error_message)
    """
    logger.info(f"Testing server command: {' '.join(command + args)}")

    # Resolve the command executable path
    resolved_command = command.copy()
    if resolved_command:
        exe_path = shutil.which(resolved_command[0])
        if exe_path:
            resolved_command[0] = exe_path
        else:
            error_msg = f"Command not found in PATH: {resolved_command[0]}"
            logger.error(error_msg)
            return (False, error_msg)

    # Prepare the full command
    full_cmd = resolved_command + args

    # Prepare the environment
    current_env = os.environ.copy()
    if env:
        logger.debug(f"Using custom environment variables: {env}")
        current_env.update(env)

    try:
        # Start the process with redirected output
        logger.debug("Launching process...")
        process = subprocess.Popen(
            full_cmd,
            env=current_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a short time to see if the process crashes immediately
        import time
        timeout = 2  # seconds
        start_time = time.time()
        
        # Poll in a loop to check if the process exits quickly
        while time.time() - start_time < timeout:
            returncode = process.poll()
            if returncode is not None:
                # Process exited quickly, which likely indicates an error
                stdout, stderr = process.communicate()
                error_msg = f"Process exited quickly with code {returncode}.\nOutput: {stderr.strip()}"
                logger.warning(error_msg)
                return (False, error_msg)
            
            # Brief pause to avoid CPU hogging
            time.sleep(0.1)
        
        # If we get here, the process survived the initial check
        logger.info("Process launched successfully, now terminating the test process")
        
        # Now terminate the process nicely
        try:
            process.terminate()
            try:
                # Wait up to 3 seconds for termination
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                logger.warning("Process did not terminate cleanly, attempting to kill")
                process.kill()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.error("Failed to kill process, it may still be running")
        except Exception as term_error:
            logger.warning(f"Error while terminating test process: {term_error}")
            # Even if termination had issues, the initial launch was successful
        
        return (True, None)
        
    except FileNotFoundError as e:
        error_msg = f"Command not found: {command[0]}"
        logger.error(error_msg)
        return (False, error_msg)
        
    except PermissionError as e:
        error_msg = f"Permission denied when running command: {e}"
        logger.error(error_msg)
        return (False, error_msg)
        
    except OSError as e:
        error_msg = f"OS error when running command: {e}"
        logger.error(error_msg)
        return (False, error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error testing command: {str(e)}"
        logger.error(error_msg)
        return (False, error_msg)


def find_claude_processes() -> List[psutil.Process]:
    """
    Find running Claude Desktop processes.
    
    Returns:
        List of Process objects representing Claude Desktop processes
    """
    claude_processes = []
    logger.info("Searching for running Claude Desktop processes...")
    
    # Possible Claude process names to search for (case-insensitive)
    claude_process_names = [
        "claude", 
        "claudedesktop",
        "claude-desktop", 
        "claude desktop",
        "anthropic claude",
        "anthropic-claude",
        "anthropic"
    ]
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                # Check process name - handle platform-specific variations
                proc_name = proc.info['name'].lower() if proc.info.get('name') else ""
                proc_exe = str(proc.info.get('exe', "")).lower()
                
                # Try to get command line for additional matching
                try:
                    cmdline = ' '.join(proc.cmdline()).lower()
                except:
                    cmdline = ""
                
                # Check if any of our potential Claude names match either the process name,
                # executable path, or command line
                matches_claude = False
                for claude_name in claude_process_names:
                    if (claude_name in proc_name or 
                        claude_name in proc_exe or 
                        claude_name in cmdline):
                        matches_claude = True
                        break
                
                if matches_claude:
                    claude_processes.append(proc)
                    logger.info(f"Found Claude process: {proc.pid} - {proc_name} - {proc_exe}")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                # Process may have terminated or we don't have permission
                logger.debug(f"Could not access process: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Error searching for Claude processes: {e}")
    
    if claude_processes:
        logger.info(f"Found {len(claude_processes)} Claude processes")
    else:
        logger.warning("No Claude processes found. You may need to start Claude manually first.")
    
    return claude_processes


def terminate_processes(processes: List[psutil.Process]) -> Tuple[bool, Optional[str]]:
    """
    Terminate the specified processes.
    
    Args:
        processes: List of Process objects to terminate
        
    Returns:
        Tuple (success, error_message)
        - If success, (True, None)
        - If error, (False, error_message)
    """
    if not processes:
        logger.info("No processes to terminate")
        return (True, None)
    
    logger.info(f"Attempting to terminate {len(processes)} processes")
    
    errors = []
    for proc in processes:
        try:
            # Get process name for logging
            try:
                name = proc.name()
            except Exception:
                name = f"PID {proc.pid}"
            
            logger.info(f"Terminating process {name} (PID: {proc.pid})")
            
            # First try to terminate gracefully
            proc.terminate()
            
            # Wait for up to 5 seconds for the process to exit
            try:
                gone, alive = psutil.wait_procs([proc], timeout=5)
                if proc in alive:
                    logger.warning(f"Process {name} (PID: {proc.pid}) did not terminate gracefully, forcing kill")
                    proc.kill()
                    gone, alive = psutil.wait_procs([proc], timeout=3)
                    if proc in alive:
                        errors.append(f"Failed to kill process {name} (PID: {proc.pid})")
                else:
                    logger.info(f"Process {name} (PID: {proc.pid}) terminated successfully")
            except psutil.TimeoutExpired:
                logger.warning(f"Timeout waiting for process {name} (PID: {proc.pid}) to terminate, forcing kill")
                proc.kill()
        
        except psutil.NoSuchProcess:
            # Process already terminated
            logger.info(f"Process {proc.pid} already terminated")
        
        except Exception as e:
            # Log any other errors
            error_msg = f"Error terminating process {proc.pid}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    # Return success only if there were no errors
    if errors:
        error_message = "\n".join(errors)
        logger.error(f"Process termination had errors: {error_message}")
        return (False, error_message)
    else:
        logger.info("All processes terminated successfully")
        return (True, None)


def start_claude_application() -> Tuple[bool, Optional[str]]:
    """
    Start the Claude Desktop application.
    
    Returns:
        Tuple (success, error_message)
        - If success, (True, None)
        - If error, (False, error_message)
    """
    logger.info("Attempting to start Claude Desktop application")
    
    try:
        # Different command for each OS
        if sys.platform == "darwin":  # macOS
            cmd = ['open', '-a', 'Claude']
            shell = False
            logger.info("Using macOS open command to launch Claude")
        elif sys.platform == "win32":  # Windows
            # Look for common Windows installation paths for Claude
            potential_paths = [
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'AnthropicClaude', 'claude.exe'),  # Known user path
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Claude', 'Claude.exe'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Claude', 'Claude.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Claude', 'Claude.exe'),
            ]
            # Check if any of the potential paths exist
            for path in potential_paths:
                if os.path.exists(path):
                    logger.info(f"Found Claude executable at {path}")
                    cmd = [path]
                    shell = False
                    break
            else:
                # If no specific path found, try using the start command
                cmd = ['start', '', 'Claude']
                shell = True
                logger.info("Using Windows start command to launch Claude")
        elif sys.platform == "linux":  # Linux
            # Try the simplest approach first - assuming 'claude' is in PATH
            cmd = ['claude']
            shell = False
            logger.info("Attempting to launch Claude using 'claude' command")
        else:
            error_msg = f"Unsupported operating system: {sys.platform}"
            logger.error(error_msg)
            return (False, error_msg)
        
        # Launch the application
        if shell:
            process = subprocess.Popen(" ".join(cmd), shell=True)
        else:
            process = subprocess.Popen(cmd)
        
        # We don't wait for completion as Claude Desktop is a GUI application
        logger.info(f"Claude Desktop launch initiated with PID {process.pid if process else 'unknown'}")
        
        # Brief pause to allow process to start
        import time
        time.sleep(1)
        
        return (True, None)
        
    except FileNotFoundError as e:
        error_msg = f"Claude Desktop application not found: {str(e)}"
        logger.error(error_msg)
        return (False, error_msg)
        
    except Exception as e:
        error_msg = f"Error starting Claude Desktop: {str(e)}"
        logger.error(error_msg)
        return (False, error_msg)