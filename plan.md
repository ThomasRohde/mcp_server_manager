Okay, let's map out the blueprint and then break it down into iterative steps and corresponding LLM prompts.

## Project Blueprint: MCP Server Manager

This project consists of a backend Python application serving both an MCP interface and a FastAPI web interface for managing other MCP servers integrated with Claude Desktop.

**Core Components:**

1.  **Configuration Storage:**
    *   `installed_servers.json`: Stores metadata for *all* registered MCP servers (managed by this tool) in a standard OS-specific application data directory (`MCPManager/`). Structure: List of objects, each with `id`, `name`, `source_type`, `source_location`, `command` (list), `arguments` (list), `environment` (dict), `enabled_in_claude` (bool).
    *   `claude_desktop_config.json`: The official Claude Desktop configuration file. This tool reads it and modifies the `mcpServers` section. Location is OS-specific.
2.  **Core Logic Module (`core_logic.py`):** Contains shared functions independent of MCP/FastAPI.
    *   Configuration path resolution.
    *   Reading/writing/parsing `installed_servers.json`.
    *   Reading/writing/parsing/modifying `claude_desktop_config.json` (`mcpServers` section).
    *   Finding registered servers by ID or name in the `installed_servers.json` data.
    *   Generating unique IDs.
    *   Testing server commands via subprocess.
    *   Finding, terminating, and starting the Claude Desktop process (`psutil`, `subprocess`).
    *   Error handling and logging wrappers.
3.  **MCP Server Module (`mcp_server.py`):**
    *   Uses the `mcp` library (`Server` or `FastMCP`).
    *   Defines MCP Resource: `mcpmanager://servers/installed` (read-only, lists servers from `installed_servers.json`).
    *   Defines MCP Tools:
        *   `install_mcp_server`: Registers a new server config, verifies command, updates `installed_servers.json`.
        *   `set_server_enabled_status`: Updates `enabled_in_claude` in `installed_servers.json` and adds/removes the server entry in `claude_desktop_config.json`.
        *   `restart_claude_desktop`: Finds, terminates, and restarts Claude Desktop.
    *   All handlers delegate work to `core_logic.py` functions.
4.  **FastAPI Web Module (`main.py` or `web_server.py`):**
    *   Serves a simple web UI using Jinja2 templates and static files (CSS/JS).
    *   Defines API Endpoints:
        *   `GET /api/servers`: Lists servers from `installed_servers.json`.
        *   `POST /api/servers`: Registers a new server (like the MCP tool).
        *   `PUT /api/servers/{identifier}/status`: Enables/disables a server (like the MCP tool).
        *   `POST /api/claude/restart`: Restarts Claude (like the MCP tool).
    *   API endpoints delegate work to `core_logic.py` functions.
    *   Serves HTML pages rendering data retrieved via the API endpoints (or directly from core logic for initial page load).
5.  **Web UI (`templates/`, `static/`):**
    *   HTML templates (e.g., `index.html`) using Jinja2.
    *   Displays server list, status toggles, restart button, registration form.
    *   Uses a CSS framework (e.g., Bootstrap served via CDN or static files) for styling.
    *   Minimal JavaScript (if needed) for triggering API calls (e.g., for toggling status, restarting) and displaying feedback.

## Iterative Implementation Plan

Here's a breakdown into smaller, incremental steps designed for safe implementation and continuous integration. Each step builds directly on the previous ones.

**Phase 1: Core Logic Foundation**

*   **Step 1: Project Setup:** Initialize project structure, virtual environment, install initial dependencies (`python-dotenv`, `psutil`, `platformdirs`). Create basic file structure (`mcp_manager/core_logic.py`, `main.py`, `.env`, `requirements.txt`).
*   **Step 2: Core Logic - Config Paths & Stubs:** Implement functions in `core_logic.py` to determine OS-specific paths for `installed_servers.json` and `claude_desktop_config.json` using `platformdirs`. Add stub functions (raising `NotImplementedError`) for all other planned core logic functions.
*   **Step 3: Core Logic - `installed_servers.json` I/O:** Implement reading and writing `installed_servers.json`. Handle file creation, empty file, JSON errors. Implement `generate_unique_id`.

**Phase 2: MCP & API Data Reading**

*   **Step 4: MCP Resource - List Servers:** Create the basic MCP Server (`mcp_server.py`) using `mcp.server.Server`. Implement `list_resources` and `read_resource` for `mcpmanager://servers/installed`, calling the core logic function (`read_installed_servers`) from Step 3. Add `mcp` library to dependencies.
*   **Step 5: FastAPI Setup & API - List Servers:** Set up a basic FastAPI app (`main.py`). Add an endpoint `GET /api/servers` that calls the *same* core logic function (`read_installed_servers`) from Step 3. Add `fastapi`, `uvicorn` to dependencies.
*   **Step 6: Web UI - Display Server List:** Configure Jinja2 templates in FastAPI. Create a basic `index.html` template. Modify the `GET /` route in FastAPI to render `index.html`, passing the server list obtained from `read_installed_servers`. Display the list (read-only) in the HTML template using Jinja2 syntax. Add `Jinja2` to dependencies. Add basic CSS (e.g., Bootstrap via CDN) for table styling.

**Phase 3: Core Actions - Restart Claude**

*   **Step 7: Core Logic - Process Management:** Implement `find_claude_processes`, `terminate_processes`, `start_claude_application` in `core_logic.py` using `psutil` and `subprocess`. Handle OS differences.
*   **Step 8: MCP Tool - Restart Claude:** Add the `restart_claude_desktop` tool to `mcp_server.py`, calling the core logic functions from Step 7.
*   **Step 9: FastAPI & UI - Restart Button:** Add a `POST /api/claude/restart` endpoint in `main.py` calling the core logic from Step 7. Add a "Restart Claude" button to `index.html` that triggers this API endpoint (e.g., using a simple HTML form or minimal JavaScript fetch). Display success/error feedback.

**Phase 4: Core Actions - Enable/Disable Servers**

*   **Step 10: Core Logic - `claude_desktop_config.json` I/O:** Implement reading, parsing, modifying (`mcpServers` section), and writing `claude_desktop_config.json` in `core_logic.py`. Handle errors gracefully.
*   **Step 11: Core Logic - Find Server:** Implement `find_server_in_list` in `core_logic.py` to locate a server entry in the list returned by `read_installed_servers` using either its `id` or unique `name`.
*   **Step 12: MCP Tool - Set Server Status:** Add the `set_server_enabled_status` tool to `mcp_server.py`, using core logic functions from Steps 3, 10, and 11.
*   **Step 13: FastAPI & UI - Enable/Disable Toggle:** Add a `PUT /api/servers/{identifier}/status` endpoint in `main.py` using core logic from Steps 3, 10, 11. Add enable/disable toggles/buttons next to each server in `index.html`. Wire them up (using HTML forms or JS fetch) to call the new API endpoint. Update the UI dynamically or refresh the page on success. Display feedback.

**Phase 5: Core Actions - Register New Server**

*   **Step 14: Core Logic - Server Verification:** Implement `test_server_command` in `core_logic.py` using `subprocess` to test-launch a server command.
*   **Step 15: MCP Tool - Install Server:** Add the `install_mcp_server` tool to `mcp_server.py`, using core logic functions from Steps 3 and 14.
*   **Step 16: FastAPI & UI - Registration Form:** Add a `POST /api/servers` endpoint in `main.py` using core logic from Steps 3 and 14. Add an HTML form to `index.html` for registering a new server (inputs for name, command, args, env, source). Submit the form to the new API endpoint. Display success/error feedback (including verification results). Refresh the server list on success.

**Phase 6: Refinement & Packaging**

*   **Step 17: Refinement:** Add proper logging throughout (`logging` module). Enhance error handling and user feedback in UI/API. Improve CSS styling. Add docstrings and type hints.
*   **Step 18: Packaging & Running:** Create `pyproject.toml` if needed. Add instructions (e.g., in `README.md`) on how to install dependencies and run the server (both MCP via `stdio` and the FastAPI web server via `uvicorn`). Consider how to run both simultaneously if needed (e.g., using `asyncio` or separate processes).

## LLM Prompts for Implementation

Here are the prompts, designed to be fed sequentially to a code-generation LLM. Each prompt assumes the context of the previously generated code.

---

**Prompt 1: Project Setup**

```text
Goal: Set up the initial project structure and dependencies for the MCP Server Manager.

1.  Create a root directory named `mcp_server_manager`.
2.  Inside `mcp_server_manager`, create:
    *   A directory named `mcp_manager`.
    *   A file named `main.py` (leave empty for now).
    *   A file named `requirements.txt`.
    *   A file named `.env` (leave empty for now).
    *   A file named `.gitignore` with standard Python ignores (like `__pycache__/`, `*.pyc`, `.env`, `venv/`).
3.  Inside the inner `mcp_manager` directory, create:
    *   An empty file named `__init__.py`.
    *   A file named `core_logic.py` (leave empty for now).
    *   A file named `mcp_server.py` (leave empty for now).
4.  Populate `requirements.txt` with the initial dependencies:
    ```
    python-dotenv
    psutil
    platformdirs
    ```
5.  Provide instructions on how to create a virtual environment (e.g., `python -m venv venv`) and install the requirements (`pip install -r requirements.txt`).
```

---

**Prompt 2: Core Logic - Config Paths & Stubs**

```text
Goal: Implement configuration path detection and create stubs for core logic functions.

Context: We have the project structure from Prompt 1. We will now modify `mcp_manager/core_logic.py`.

1.  In `mcp_manager/core_logic.py`, import necessary libraries: `os`, `pathlib`, `platformdirs`, `logging`, `json`, `subprocess`, `psutil`, `sys`, `uuid`, `typing` (`List`, `Dict`, `Optional`, `Tuple`, `Any`).
2.  Set up basic logging configuration at the top of the file.
3.  Define constants for the application name (`APP_NAME = "MCPManager"`) and the filenames (`INSTALLED_SERVERS_FILENAME = "installed_servers.json"`, `CLAUDE_CONFIG_FILENAME = "claude_desktop_config.json"`).
4.  Implement a function `get_config_path(filename: str) -> pathlib.Path`:
    *   Use `platformdirs.user_data_dir(APP_NAME)` to get the base application data directory.
    *   Return the full path to the specified `filename` within that directory. Ensure the directory exists using `os.makedirs(exist_ok=True)`.
    *   Add docstrings and type hints.
5.  Implement a function `get_claude_config_path() -> pathlib.Path`:
    *   Determine the path to `claude_desktop_config.json` based on the OS (`sys.platform`).
        *   macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
        *   Windows: `%APPDATA%\Claude\claude_desktop_config.json` (use `os.getenv('APPDATA')`)
        *   Linux: `~/.config/Claude/claude_desktop_config.json` (Consider Flatpak path too if possible, but prioritize the standard one).
    *   Return the `pathlib.Path` object. Use `pathlib.Path.home()` for `~`.
    *   Add docstrings and type hints. Handle potential errors like `APPDATA` not being set.
6.  Add stub functions (with correct type hints and docstrings indicating their future purpose) that raise `NotImplementedError` for the following planned core logic functions:
    *   `read_installed_servers() -> List[Dict[str, Any]]`
    *   `write_installed_servers(servers: List[Dict[str, Any]]) -> None`
    *   `generate_unique_id() -> str`
    *   `find_server_in_list(servers: List[Dict[str, Any]], identifier: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]`
    *   `read_claude_config() -> Dict[str, Any]`
    *   `write_claude_config(config: Dict[str, Any]) -> None`
    *   `update_claude_mcp_servers_section(config: Dict[str, Any], server_name: str, server_details: Optional[Dict[str, Any]]) -> Dict[str, Any]`
    *   `test_server_command(command: List[str], args: List[str], env: Optional[Dict[str, str]]) -> Tuple[bool, Optional[str]]`
    *   `find_claude_processes() -> List[psutil.Process]`
    *   `terminate_processes(processes: List[psutil.Process]) -> Tuple[bool, Optional[str]]`
    *   `start_claude_application() -> Tuple[bool, Optional[str]]`
```

---

**Prompt 3: Core Logic - `installed_servers.json` I/O**

```text
Goal: Implement reading/writing `installed_servers.json` and generating unique IDs.

Context: We have `mcp_manager/core_logic.py` with config path functions and stubs from Prompt 2.

1.  In `mcp_manager/core_logic.py`, implement the actual logic for the following functions, replacing the `NotImplementedError`:
    *   `generate_unique_id() -> str`: Generate a unique string ID (e.g., using `uuid.uuid4()`).
    *   `read_installed_servers() -> List[Dict[str, Any]]`:
        *   Get the path using `get_config_path(INSTALLED_SERVERS_FILENAME)`.
        *   Try to read the file. If it doesn't exist or is empty, return `[]`.
        *   If it exists, try to parse it as JSON.
        *   Handle `FileNotFoundError` (return `[]`), `json.JSONDecodeError` (log error, return `[]`), and other potential `IOError`s (log error, return `[]`).
        *   Return the parsed list of server dictionaries. Ensure proper error logging.
    *   `write_installed_servers(servers: List[Dict[str, Any]]) -> None`:
        *   Get the path using `get_config_path(INSTALLED_SERVERS_FILENAME)`.
        *   Ensure the directory exists.
        *   Write the `servers` list to the file as JSON with indentation (e.g., `json.dump(servers, f, indent=2)`).
        *   Handle potential `IOError`s during writing and log errors.
2.  Ensure all implemented functions have clear docstrings and correct type hints.
```

---

**Prompt 4: MCP Resource - List Servers**

```text
Goal: Implement the MCP server and its resource to list installed servers.

Context: We have the core logic for reading `installed_servers.json` in `mcp_manager/core_logic.py` (Prompt 3). We will now implement `mcp_manager/mcp_server.py`.

1.  Add `mcp` to `requirements.txt` and instruct the user to reinstall dependencies.
2.  In `mcp_manager/mcp_server.py`, import necessary components: `logging`, `json`, `mcp.server.Server`, `mcp.types`, `asyncio`. Also import `core_logic` functions: `read_installed_servers`.
3.  Set up basic logging.
4.  Create an MCP `Server` instance: `server = Server("mcp-server-manager")`.
5.  Implement the `@server.list_resources()` handler:
    *   Return a list containing one `mcp.types.Resource` object.
    *   Use URI `mcpmanager://servers/installed`.
    *   Provide appropriate `name`, `description`, and `mimeType="application/json"`.
6.  Implement the `@server.read_resource()` handler:
    *   Check if the requested `uri` matches `mcpmanager://servers/installed`. If not, raise `ValueError`.
    *   Call `core_logic.read_installed_servers()` to get the list of servers.
    *   Handle potential exceptions from `read_installed_servers` by logging and re-raising or returning an appropriate MCP error if the framework supports it.
    *   Serialize the resulting list to a JSON string using `json.dumps()`.
    *   Return the JSON string.
7.  Add stub handlers (raising `NotImplementedError`) for `@server.list_tools()` and `@server.call_tool()`.
8.  Add an `async def main_mcp():` function that initializes and runs the MCP server using `mcp.server.stdio.stdio_server()`. Include basic `InitializationOptions`.
9.  Add an `if __name__ == "__main__":` block that runs `asyncio.run(main_mcp())` for testing the MCP server independently.
```

---

**Prompt 5: FastAPI Setup & API - List Servers**

```text
Goal: Set up the FastAPI application and an API endpoint to list installed servers.

Context: We have core logic for reading servers (Prompt 3) and a separate MCP server (Prompt 4). We will now modify `main.py`.

1.  Add `fastapi`, `uvicorn[standard]`, `Jinja2`, `python-multipart` (for forms later) to `requirements.txt` and instruct the user to reinstall dependencies.
2.  In `main.py`, import necessary components: `FastAPI`, `Request`, `Depends`, `HTTPException`, `status` from `fastapi`; `List`, `Any`, `Dict` from `typing`; `Jinja2Templates` from `fastapi.templating`; `Path` from `pathlib`.
3.  Import the relevant core logic function: `from mcp_manager.core_logic import read_installed_servers`.
4.  Create a `FastAPI` app instance: `app = FastAPI()`.
5.  Implement an API endpoint `GET /api/servers`:
    *   Define an `async def get_servers_api():`.
    *   Inside the function, call `core_logic.read_installed_servers()`.
    *   Handle potential exceptions (though `read_installed_servers` should handle file errors internally and return `[]`). If needed, add a try/except block and raise an `HTTPException(status_code=500, detail="...")` on failure.
    *   Return the list of servers. FastAPI will automatically convert it to JSON.
6.  Add basic `uvicorn` run command instructions in comments or a docstring (e.g., `uvicorn main:app --reload`).
```

---

**Prompt 6: Web UI - Display Server List**

```text
Goal: Create a basic web page using FastAPI and Jinja2 to display the list of servers.

Context: We have a FastAPI app (`main.py` from Prompt 5) with an API endpoint `/api/servers`. We need to serve an HTML page.

1.  In the root `mcp_server_manager` directory, create:
    *   A directory named `templates`.
    *   A directory named `static` (leave empty for now).
2.  In `main.py`:
    *   Configure Jinja2 templates: `templates = Jinja2Templates(directory="templates")`.
    *   Add an endpoint `GET /` (for the root path):
        *   Define an `async def get_root_page(request: Request):`.
        *   Call `core_logic.read_installed_servers()` to get the server list. Handle errors as in the API endpoint.
        *   Return `templates.TemplateResponse("index.html", {"request": request, "servers": server_list})`.
3.  Create the `templates/index.html` file:
    *   Add basic HTML structure (html, head, body).
    *   In the `<head>`, link to Bootstrap CSS via CDN for basic styling (e.g., from `bootstrapcdn.com`). Add a `<title>MCP Server Manager</title>`.
    *   In the `<body>`:
        *   Add a container (`<div class="container mt-4">`).
        *   Add a heading (`<h1>MCP Server Manager</h1>`).
        *   Add a section heading (`<h2>Registered Servers</h2>`).
        *   Check if the `servers` list passed from FastAPI is empty. If so, display a message like "No servers registered yet."
        *   If not empty, create an HTML table (`<table class="table table-striped">`).
        *   Include table headers (`<thead>`): Name, Status, Command, Source.
        *   Use a Jinja2 `for` loop (`{% for server in servers %}`) to iterate through the `servers` list and create table rows (`<tbody><tr>...</tr></tbody>`).
        *   Display `server.name`, `server.enabled_in_claude` (as "Enabled"/"Disabled"), `server.command[0]`, and `server.source_type`/`server.source_location` in table cells (`<td>`). Use Jinja2 expressions `{{ server.field_name }}`.
4.  Ensure the `uvicorn` command can run and serve the page correctly, displaying the (currently empty) list of servers.
```

---

**Prompt 7: Core Logic - Process Management**

```text
Goal: Implement core logic functions for finding, terminating, and starting Claude Desktop.

Context: We have `mcp_manager/core_logic.py` with implemented JSON I/O and stubs for process management (from Prompt 2/3).

1.  In `mcp_manager/core_logic.py`, implement the actual logic for the following functions, replacing `NotImplementedError`:
    *   `find_claude_processes() -> List[psutil.Process]`:
        *   Iterate through `psutil.process_iter(['pid', 'name'])`.
        *   Identify processes named 'Claude' (case-insensitive might be safer). Handle potential `psutil` exceptions (`NoSuchProcess`, `AccessDenied`).
        *   Consider platform differences in executable names if necessary (e.g., 'Claude.exe' on Windows).
        *   Return a list of matching `psutil.Process` objects.
    *   `terminate_processes(processes: List[psutil.Process]) -> Tuple[bool, Optional[str]]`:
        *   Iterate through the provided list of processes.
        *   For each process, try `proc.terminate()`. Wait briefly using `proc.wait(timeout=...)` (e.g., 3-5 seconds).
        *   If `terminate()` fails or times out, consider trying `proc.kill()`.
        *   Catch exceptions (`psutil.NoSuchProcess`, `psutil.TimeoutExpired`, `Exception`).
        *   Log successes and failures.
        *   Return `(True, None)` on overall success, or `(False, "Error message...")` if any termination failed.
    *   `start_claude_application() -> Tuple[bool, Optional[str]]`:
        *   Use `subprocess.Popen` to launch Claude.
        *   Determine the command based on OS:
            *   macOS: `['open', '-a', 'Claude']`
            *   Windows: Try `['start', '', 'Claude']` with `shell=True`, or find the executable path if necessary (more complex). Start simple.
            *   Linux: Find the executable (e.g., `claude`, `/opt/Claude/claude`, or via `.desktop` file lookup - start simple with just assuming `claude` is in PATH).
        *   Use `subprocess.Popen` without waiting for completion.
        *   Wrap in try/except `FileNotFoundError` and `Exception`.
        *   Log success or failure.
        *   Return `(True, None)` on success, `(False, "Error message...")` on failure.
2.  Ensure functions have docstrings, type hints, and proper logging.
```

---

**Prompt 8: MCP Tool - Restart Claude**

```text
Goal: Implement the MCP tool to restart Claude Desktop.

Context: We have the core logic for process management (Prompt 7) and the basic MCP server structure (`mcp_server.py` from Prompt 4).

1.  In `mcp_manager/mcp_server.py`:
    *   Import the necessary core logic functions: `find_claude_processes`, `terminate_processes`, `start_claude_application`.
    *   Implement the `@server.list_tools()` handler (replace the stub):
        *   Return a list containing one `mcp.types.Tool` definition for `restart_claude_desktop`.
        *   Include `name`, `description`, and an empty `inputSchema` (no arguments needed).
    *   Implement the `@server.call_tool()` handler (replace the stub):
        *   Check if the requested `name` is `restart_claude_desktop`. If not, raise `ValueError`.
        *   Call `core_logic.find_claude_processes()`.
        *   Call `core_logic.terminate_processes()` with the found processes. If termination fails, return an `mcp.types.TextContent` error result immediately.
        *   **(Optional but recommended):** Add a short `asyncio.sleep(1)` after termination.
        *   Call `core_logic.start_claude_application()`.
        *   Based on the success/failure results of terminate/start, construct a result dictionary (e.g., `{"status": "success/error", "message": "..."}`).
        *   Return the result as `[mcp.types.TextContent(type="text", text=json.dumps(result, indent=2))]`.
2.  Ensure error handling is robust and clear messages are returned.
```

---

**Prompt 9: FastAPI & UI - Restart Button**

```text
Goal: Add a restart button to the web UI and connect it to a FastAPI endpoint.

Context: We have the core process logic (Prompt 7), the web page displaying servers (`main.py`, `templates/index.html` from Prompt 6).

1.  In `main.py`:
    *   Import the necessary core logic functions: `find_claude_processes`, `terminate_processes`, `start_claude_application`.
    *   Add a new FastAPI endpoint `POST /api/claude/restart`:
        *   Define `async def restart_claude_api():`.
        *   Call `core_logic.find_claude_processes()`.
        *   Call `core_logic.terminate_processes()`. If fails, raise `HTTPException(500, detail=error_message)`.
        *   Call `core_logic.start_claude_application()`. If fails, raise `HTTPException(500, detail=error_message)`.
        *   If successful, return `{"status": "success", "message": "Claude Desktop restarted successfully."}`.
2.  In `templates/index.html`:
    *   Add a "Restart Claude Desktop" button, perhaps near the top heading. Style it using Bootstrap classes (`btn btn-warning`).
    *   Add a small amount of JavaScript (either inline `<script>` or in a separate `static/js/main.js` file, which would require configuring static files in FastAPI).
    *   The JavaScript should:
        *   Add an event listener to the button.
        *   On click, use the `fetch` API to make a `POST` request to `/api/claude/restart`.
        *   Handle the response:
            *   Display a success message (e.g., using `alert()` or updating a dedicated message area on the page) if the API returns success.
            *   Display an error message if the API returns an error (e.g., from `HTTPException`).
        *   Optionally, disable the button while the request is in progress.
3.  If using a separate JS file, ensure FastAPI is configured to serve static files:
    *   `from fastapi.staticfiles import StaticFiles`
    *   `app.mount("/static", StaticFiles(directory="static"), name="static")`
    *   Link the JS file in `index.html`: `<script src="/static/js/main.js"></script>`.
```

---

**Prompt 10: Core Logic - `claude_desktop_config.json` I/O**

```text
Goal: Implement core logic for reading, modifying, and writing the Claude Desktop config file.

Context: We have `mcp_manager/core_logic.py` with stubs for Claude config handling (Prompt 2).

1.  In `mcp_manager/core_logic.py`, implement the actual logic for:
    *   `read_claude_config() -> Dict[str, Any]`:
        *   Get the path using `get_claude_config_path()`.
        *   Handle `FileNotFoundError` by returning an empty dictionary `{}` (representing a non-existent or empty config).
        *   Read the file and parse JSON. Handle `json.JSONDecodeError` and `IOError` by logging the error and returning `{}`.
        *   Return the parsed dictionary.
    *   `write_claude_config(config: Dict[str, Any]) -> None`:
        *   Get the path using `get_claude_config_path()`.
        *   Ensure the directory exists.
        *   Write the `config` dictionary to the file as JSON with indentation (`indent=2`).
        *   Handle `IOError` and log errors.
    *   `update_claude_mcp_servers_section(config: Dict[str, Any], server_name: str, server_details: Optional[Dict[str, Any]]) -> Dict[str, Any]`:
        *   Ensure `config['mcpServers']` exists, initializing it to `{}` if not.
        *   If `server_details` is `None`:
            *   Remove `server_name` from `config['mcpServers']` if it exists (`config['mcpServers'].pop(server_name, None)`).
        *   If `server_details` is a dictionary:
            *   Add/update the entry: `config['mcpServers'][server_name] = server_details`.
        *   Return the modified `config` dictionary.
2.  Ensure functions have docstrings, type hints, and proper logging.
```

---

**Prompt 11: Core Logic - Find Server**

```text
Goal: Implement the core logic function to find a server in the installed list by ID or name.

Context: We have `mcp_manager/core_logic.py` with the stub for `find_server_in_list` (Prompt 2) and implemented `read_installed_servers` (Prompt 3).

1.  In `mcp_manager/core_logic.py`, implement the actual logic for:
    *   `find_server_in_list(servers: List[Dict[str, Any]], identifier: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]`:
        *   Iterate through the `servers` list.
        *   First, check if any `server['id']` matches the `identifier`. If found, return `(server, None)`.
        *   If no ID match, iterate again (or use a list comprehension/filter) to find all servers where `server['name']` matches the `identifier`.
        *   If exactly one name match is found, return `(found_server, None)`.
        *   If zero name matches are found, return `(None, f"No server found with identifier '{identifier}'.")`.
        *   If multiple name matches are found, return `(None, f"Multiple servers found with name '{identifier}'. Use unique ID.")`.
2.  Ensure the function has docstrings and type hints.
```

---

**Prompt 12: MCP Tool - Set Server Status**

```text
Goal: Implement the MCP tool to enable/disable servers and update Claude config.

Context: We have core logic for `installed_servers.json` I/O (Prompt 3), Claude config I/O (Prompt 10), finding servers (Prompt 11), and the MCP server structure (`mcp_server.py` from Prompt 8).

1.  In `mcp_manager/mcp_server.py`:
    *   Import necessary core logic functions: `read_installed_servers`, `write_installed_servers`, `find_server_in_list`, `read_claude_config`, `update_claude_mcp_servers_section`, `write_claude_config`.
    *   Update the `@server.list_tools()` handler:
        *   Add the `mcp.types.Tool` definition for `set_server_enabled_status`.
        *   Define its `inputSchema` according to the spec: requires `enabled` (boolean), and *either* `server_id` (string) or `server_name` (string). Use JSON schema properties and `oneOf` or similar logic if possible, or describe the requirement clearly in the description.
    *   Update the `@server.call_tool()` handler:
        *   Add logic to handle the `set_server_enabled_status` tool call.
        *   Extract `arguments` from the request (`server_id`, `server_name`, `enabled`).
        *   Validate that exactly one of `server_id` or `server_name` is provided. If not, return an error `TextContent`.
        *   Determine the `identifier` (either `server_id` or `server_name`).
        *   Call `core_logic.read_installed_servers()`.
        *   Call `core_logic.find_server_in_list()` using the `identifier`. If not found or ambiguous, return an error `TextContent` with the message from `find_server_in_list`.
        *   Update the found server's `enabled_in_claude` field in the list.
        *   Call `core_logic.write_installed_servers()` with the updated list. Handle potential errors.
        *   Call `core_logic.read_claude_config()`.
        *   Prepare the `server_details` for Claude config: If `enabled` is true, construct the dictionary `{ "command": server['command'][0], "args": server['command'][1:] + server['arguments'], "env": server['environment'] }` (only include `env` if it's not empty). If `enabled` is false, set `server_details = None`.
        *   Call `core_logic.update_claude_mcp_servers_section()` with the config, server name (`found_server['name']`), and prepared `server_details`.
        *   Call `core_logic.write_claude_config()` with the modified config. Handle potential errors.
        *   Construct a success message (e.g., `{"status": "success", "message": "Server '{name}' status updated. Restart Claude."}`).
        *   Return the success/error message as `[mcp.types.TextContent(...)]`.
2.  Ensure robust error handling at each step (reading/writing files, finding server).
```

---

**Prompt 13: FastAPI & UI - Enable/Disable Toggle**

```text
Goal: Add enable/disable controls to the web UI and connect them to a FastAPI endpoint.

Context: We have core logic for status updates (Prompts 3, 10, 11), the web page listing servers (`main.py`, `templates/index.html` from Prompt 6/9).

1.  In `main.py`:
    *   Import necessary core logic functions (as used in Prompt 12).
    *   Add a new endpoint `PUT /api/servers/{identifier}/status`:
        *   Define `async def set_server_status_api(identifier: str, payload: Dict[str, bool])`. The payload should contain `{"enabled": true/false}`.
        *   Get `enabled = payload.get('enabled')`. Validate it's a boolean.
        *   Perform the same core logic steps as in the MCP tool (Prompt 12): read installed, find server (using `identifier`), update `enabled_in_claude`, write installed, read claude config, prepare details, update claude section, write claude config.
        *   Return appropriate success JSON `{"status": "success", "message": "..."}` or raise `HTTPException` on errors (e.g., 404 if server not found, 400 for bad input, 500 for file errors).
2.  In `templates/index.html`:
    *   Modify the server list table. Add a new column for "Actions".
    *   In the actions cell for each server, add a toggle switch (using Bootstrap's switch component or simple buttons like "Enable"/"Disable").
    *   The state of the switch/button should reflect the server's current `enabled_in_claude` status.
    *   Add JavaScript (inline or in `static/js/main.js`):
        *   Add event listeners to the toggle switches/buttons.
        *   On change/click, determine the server identifier (use the `server.id` or `server.name` - `id` is safer) and the desired new status (`true` or `false`).
        *   Use `fetch` to make a `PUT` request to `/api/servers/{identifier}/status` with the JSON payload `{"enabled": new_status}`. Include appropriate headers (`'Content-Type': 'application/json'`).
        *   Handle the response: Update the switch/button's visual state on success. Display success/error messages (e.g., remind user to restart Claude). Consider refreshing the whole server list or just updating the specific row visually.
```

---

**Prompt 14: Core Logic - Server Verification**

```text
Goal: Implement the core logic function to test if a server command can be launched.

Context: We have `mcp_manager/core_logic.py` with the stub for `test_server_command` (Prompt 2).

1.  In `mcp_manager/core_logic.py`, implement the actual logic for:
    *   `test_server_command(command: List[str], args: List[str], env: Optional[Dict[str, str]]) -> Tuple[bool, Optional[str]]`:
        *   Prepare the full command list: `full_cmd = command + args`.
        *   Prepare the environment: Get the current environment using `os.environ.copy()`. If `env` is provided, update the copy with `env.update(provided_env)`.
        *   Use `subprocess.Popen(full_cmd, env=current_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)` to start the process. Redirect stdout/stderr to avoid polluting the manager's output.
        *   Wrap the `Popen` call in a try/except block to catch `FileNotFoundError` (command not found) and other potential OS errors. Return `(False, "Command not found/...")` if caught.
        *   Immediately after `Popen`, wait for a very short time using `process.poll()` in a loop or `process.wait(timeout=...)` (e.g., timeout=1 or 2 seconds).
        *   If `process.poll()` returns a non-None value (or `wait()` returns) within the timeout, it means the process exited quickly. Capture `stdout`/`stderr` using `process.communicate()` and return `(False, f"Process exited quickly with code {process.returncode}. Output: {stderr}")`.
        *   If the process is still running after the short wait (`process.poll()` is `None`), assume it launched successfully *for now*.
        *   Reliably terminate the test process using `process.terminate()` and potentially `process.kill()` if termination fails (similar logic to `terminate_processes`). Capture any errors during this test termination.
        *   If the launch seemed okay (didn't crash instantly) return `(True, None)`.
        *   If termination of the *test* process failed, log it but still return `(True, None)` if the initial launch seemed okay, maybe adding a warning to the log.
2.  Ensure the function has docstrings, type hints, handles errors, and provides informative error messages in the return tuple.
```

---

**Prompt 15: MCP Tool - Install Server**

```text
Goal: Implement the MCP tool to register and verify a new server configuration.

Context: We have core logic for `installed_servers.json` I/O (Prompt 3), unique IDs (Prompt 3), server verification (Prompt 14), and the MCP server structure (`mcp_server.py`).

1.  In `mcp_manager/mcp_server.py`:
    *   Import necessary core logic functions: `read_installed_servers`, `write_installed_servers`, `generate_unique_id`, `test_server_command`.
    *   Update `@server.list_tools()`: Add the `mcp.types.Tool` definition for `install_mcp_server`. Define its `inputSchema` to require `name` (string), `command` (list of strings), `args` (list of strings). Optional inputs: `environment` (object/dict), `source_type` (string), `source_location` (string).
    *   Update `@server.call_tool()`:
        *   Add logic to handle the `install_mcp_server` tool call.
        *   Extract arguments: `name`, `command`, `args`, `environment`, `source_type`, `source_location`. Validate required fields. Ensure `command` is not empty.
        *   Call `core_logic.test_server_command(command, args, environment)`.
        *   If `test_server_command` returns `False`, construct an error message using the returned reason and return it as `[mcp.types.TextContent(...)]`. Do not save anything.
        *   If `test_server_command` returns `True`:
            *   Call `core_logic.generate_unique_id()`.
            *   Create the new server dictionary object using all provided inputs, the generated ID, and setting `enabled_in_claude=False`. Remember `args` from input are the *user-specified* arguments, different from the base arguments potentially included in the `command` list. Let's rename the input schema field for user arguments to `user_arguments` to avoid confusion with the `command` list's arguments. Store it as `arguments` in the JSON. **Correction**: Let's stick to the blueprint: input schema has `command` (list like `["python", "script.py"]`) and `arguments` (list like `["--port", "8000"]`). The `test_server_command` will use `command + arguments`. The JSON will store `command` and `arguments` separately.
            *   Call `core_logic.read_installed_servers()`.
            *   Append the new server object to the list.
            *   Call `core_logic.write_installed_servers()` with the updated list. Handle errors.
            *   Construct a success message `{"status": "success", "message": "Server '{name}' registered and verified."}`.
            *   Return the success message as `[mcp.types.TextContent(...)]`.
```

---

**Prompt 16: FastAPI & UI - Registration Form**

```text
Goal: Add a form to the web UI for registering new servers via a FastAPI endpoint.

Context: We have core logic for installation/verification (Prompts 3, 14), the web page (`main.py`, `templates/index.html`), and other UI elements.

1.  In `main.py`:
    *   Import necessary core logic functions (as used in Prompt 15).
    *   Add Pydantic models (or use `fastapi.Form`) to define the expected input for the registration: `name: str`, `command_str: str` (user enters command + base args as string), `arguments_str: str` (user enters user args as string), `environment_str: str` (user enters env vars as string), `source_type: Optional[str]`, `source_location: Optional[str]`.
    *   Add a new endpoint `POST /api/servers`:
        *   Define `async def register_server_api(form_data: ... = Depends(YourModel.as_form))`. Use `Form(...)` if not using Pydantic models for form data.
        *   Parse the input strings:
            *   Split `command_str` into a list (`command`). Handle quotes if necessary (or keep simple splitting by space first). Validate the list is not empty.
            *   Split `arguments_str` into a list (`arguments`).
            *   Parse `environment_str` (e.g., split lines, then split by `=`) into a dictionary (`environment`). Handle parsing errors.
        *   Perform the same core logic steps as in the MCP tool (Prompt 15): `test_server_command`, if success -> `generate_unique_id`, create server dict, `read_installed_servers`, append, `write_installed_servers`.
        *   Return success JSON `{"status": "success", "message": "..."}` or raise `HTTPException` with appropriate status codes (400 for bad input/parsing, 409 or 400 if verification fails, 500 for file errors) and details.
2.  In `templates/index.html`:
    *   Add an HTML `<form>` section for registering a new server. Use Bootstrap form styling.
    *   Include input fields (`<input>`, `<textarea>`) corresponding to the API endpoint's expected form data: Name, Command (string), Arguments (string), Environment (textarea, one `KEY=VALUE` per line), optional Source Type (dropdown), optional Source Location. Label them clearly.
    *   Set the form's `method="POST"` and `action="/api/servers"` (or use JavaScript).
    *   Add a submit button (`<button type="submit">Register Server</button>`).
    *   Add JavaScript (or handle form submission response):
        *   Intercept the form submission using JavaScript (prevent default).
        *   Gather form data.
        *   Use `fetch` to make a `POST` request to `/api/servers` with the form data (`FormData` object or similar).
        *   Handle the response: Display success or error messages prominently near the form. If successful, clear the form and ideally refresh the server list displayed on the page (e.g., by reloading the page or fetching the list again via `GET /api/servers` and re-rendering the table).
```

---

**Prompt 17: Refinement**

```text
Goal: Refine the application with logging, better error handling, UI improvements, docstrings, and type hints.

Context: We have a mostly functional application from Prompts 1-16.

1.  **Logging:** Review all `.py` files (`core_logic.py`, `mcp_server.py`, `main.py`). Ensure consistent and informative logging is used (`logging.info`, `logging.warning`, `logging.error`, `logging.exception`) for key operations, file access, process management, API requests, and errors.
2.  **Error Handling:**
    *   Review all `try...except` blocks. Ensure specific exceptions are caught where possible.
    *   Ensure user-facing errors (API responses, UI messages) are clear and don't expose sensitive details. Provide guidance where appropriate (e.g., "Check file permissions", "Ensure command is in PATH").
    *   Standardize the JSON response format for API errors (e.g., `{"detail": "error message"}` which FastAPI uses with `HTTPException`).
3.  **UI Improvements:**
    *   Review `templates/index.html` and any JS. Improve layout, spacing, and visual feedback using the chosen CSS framework (Bootstrap).
    *   Make sure loading states are indicated for buttons (Restart, Enable/Disable, Register).
    *   Ensure error/success messages are displayed clearly and can be dismissed.
    *   Consider adding simple client-side validation to the registration form (e.g., required fields).
4.  **Docstrings & Type Hints:** Review all functions and methods. Ensure comprehensive docstrings explaining purpose, arguments, and return values. Ensure accurate type hints are present for all function signatures and variables where practical.
5.  **Code Cleanup:** Remove any unused imports, variables, or commented-out code. Ensure consistent code style (e.g., adhere to PEP 8).
```

---

**Prompt 18: Packaging & Running**

```text
Goal: Finalize packaging setup and provide instructions for running the application.

Context: The refined application code from Prompt 17.

1.  Create/Update `pyproject.toml`: If desired for modern packaging, create a `pyproject.toml` file. Define project metadata (name, version, authors), dependencies (sync with `requirements.txt`), and potentially entry points if creating a installable package. Alternatively, ensure `requirements.txt` is complete and accurate.
2.  Create `README.md`:
    *   Add a brief description of the project (MCP Server Manager).
    *   List prerequisites (Python 3.x, pip).
    *   Provide clear, step-by-step instructions:
        *   Cloning the repository (if applicable).
        *   Creating a virtual environment.
        *   Installing dependencies (`pip install -r requirements.txt` or `pip install .` if using `pyproject.toml`).
        *   How to run the FastAPI web server (`uvicorn main:app --host 0.0.0.0 --port 8000`). Explain the host/port.
        *   How to run the MCP server interface (e.g., `python -m mcp_manager.mcp_server` if structured as a package, or `python mcp_manager/mcp_server.py`).
        *   Explain that the user likely needs to run the FastAPI server to use the web UI. Discuss how the MCP part might be registered with Claude Desktop (e.g., manually adding its command to `claude_desktop_config.json`, perhaps pointing to a wrapper script that runs `mcp_server.py`). **Note:** Running both FastAPI and MCP simultaneously from one command is tricky. For simplicity, instruct running them separately or focus the instructions on running FastAPI for the UI, assuming the MCP tools are primarily invoked via the UI's API calls to the shared core logic. *Self-correction:* The goal *was* to have an MCP server *as well*. A better approach might be to structure `main.py` to optionally run the MCP server in the background using `asyncio.create_task` when `uvicorn` starts, or suggest running `python mcp_manager/mcp_server.py` separately if needed for direct MCP interaction. Let's refine the instructions to recommend running FastAPI via uvicorn for the UI, and running `python mcp_manager/mcp_server.py` separately if direct MCP access is needed.
3.  Final Check: Ensure all necessary files (`.gitignore`, `README.md`, requirements/pyproject.toml, source code) are present and consistent.
```

This detailed plan and series of prompts provide a structured path to implement the MCP Server Manager, focusing on incremental development and integration.