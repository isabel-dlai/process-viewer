# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Process Viewer is a real-time web-based process monitoring application that intelligently identifies and displays running development processes with live previews. Built with Flask, Socket.IO, and vanilla JavaScript, it provides a modern UI for monitoring Python, Node.js, Ruby, and containerized applications.

## Development Commands

```bash
# Install dependencies (using uv package manager - NEVER use pip)
uv init
uv add flask flask-socketio flask-cors psutil python-socketio

# Run the application
uv run python app.py
# App runs on http://localhost:5555

# Kill all running instances (if needed)
pkill -f "python app.py"
```

## Architecture & Key Components

### Core Files
- **app.py**: Flask server with Socket.IO handlers. Emits 'process_update' events every 2 seconds with process data and system info.
- **process_identifier.py**: Smart process categorization engine (580 LOC) that identifies app types, extracts meaningful names, and filters ports.
- **process_monitor.py**: Queries system processes using psutil, focuses on development-related processes.

### Frontend Architecture
- **static/js/app.js**: Implements DOM reconciliation pattern with `previewManager` object
- **templates/**: Jinja2 templates with base.html and index.html
- Uses WebSocket for real-time updates, no REST API endpoints
- **Preview-only UI**: Shows only app preview cards, no process table or controls

### App Preview Grouping Logic

The app intelligently groups related processes to provide a clean, organized view:

#### Two-Pass Grouping Algorithm (app.js:270-375)

**Pass 1: Same-Directory Grouping**
- Merges multiple backend processes in the same directory (e.g., multiple Python workers)
- Primary process becomes the main app, others are added to `related_processes` as "Backend Instance"
- Prevents duplicate cards for the same service

**Pass 2: Frontend/Backend Pairing**
- Detects frontend/backend pairs across different directories
- Checks for common project root (e.g., `/drawing-tutor/frontend` and `/drawing-tutor/backend`)
- Validates directory names contain "frontend" and "backend"
- Bundles backend as a related process under the frontend card
- Backend processes are removed from the main app list

#### Display Structure

**Single App Card:**
- Shows zoomed-out iframe preview of the app (1280x800 scaled to 30%)
- Port badge to open in browser
- Clickable preview overlay to open app in new tab
- Bundled processes section below showing:
  - Backend Server (with clickable port link)
  - Backend Instances (multiple workers)
  - Package Managers (UV, npm, yarn)
  - Bundlers (Vite, Webpack, esbuild)
  - Virtual Environments
  - Auto-restart tools (Nodemon)

**Result:** Frontends are the primary focus with thumbnail preview access, while backends and supporting processes are neatly organized underneath.

### Critical Implementation Details

#### Iframe Previews
- Iframes are set to 1280x800px (standard desktop size) and scaled to 30% using CSS transforms
- Creates a thumbnail effect showing the full app layout
- Iframes have `pointer-events: none` with clickable overlay on top to open in new tab
- Each preview is 240px tall (800 * 0.3) to properly contain the scaled iframe
- Uses `transform-origin: top left` to ensure scaling happens from top-left corner

#### Port Detection (Lines 84-109 in process_identifier.py)
Ports are filtered to web-friendly ranges:
- Common ports: 3000-3010, 4000-4010, 5000-5010, 7860-7870, 8000-8100, 8500-8510, 9000-9100
- Excludes ephemeral range (49000-65535)
- Streamlit apps specifically on 8501-8503

#### Process Filtering
- Excludes IDEs (VS Code, Vim, Emacs, etc.)
- Excludes Git operations
- Focuses on user processes in /Users or /home directories
- Identifies processes by command line analysis, not just name

#### Related Processes Detection (process_identifier.py:518-595)
The backend automatically detects and bundles related processes:
- **Package Managers**: UV, npm, yarn, pnpm (same working directory)
- **Virtual Environments**: .venv, virtualenv, pipenv processes
- **Build Tools**: Webpack, Vite, esbuild bundlers
- **Auto-restart**: Nodemon processes
- **Workers**: Celery, RQ, Huey worker processes
- **Web Server Workers**: Gunicorn, Uvicorn child processes

Each main process includes a `related_processes` array with:
```python
{
    'pid': int,
    'name': str,
    'type': str,  # e.g., "Package Manager (UV)", "Backend Server"
    'cpu_percent': float,
    'memory_mb': float,
    'cmdline': list,  # First 3 args
    'ports': list     # For backend servers
}
```

## Common Issues & Solutions

### Streamlit/Gradio Apps Not Showing
- Check port is in `common_web_ports` list (lines 84-93 in process_identifier.py)
- Verify process has 'streamlit' in command line for proper detection (lines 338-349)
- Ensure port range includes your app (e.g., 8500-8510 for Streamlit)

### Apps Not Showing Up
- Check browser console for JavaScript errors
- Verify processes have ports in the allowed ranges
- Ensure `renderAppPreviews()` function is being called
- Check that previewManager reconciliation logic is working

### Process Not Detected
- Check `get_user_processes()` filtering logic
- Verify process isn't being excluded as IDE/Git
- Add specific detection in command line parsing section

## WebSocket Events

### Client → Server
- `get_processes`: Request process list

### Server → Client
- `process_update`: Emitted every 2 seconds with `{processes: [], system_info: {}}`

## Frontend State Management

The frontend maintains simple state for efficient updates:
- `previewManager.cards`: DOM elements for preview cards (Map by groupId)
- `processes`: Array of current process data

Updates follow this flow:
1. Socket.IO emits 'process_update' every 2 seconds
2. `renderAppPreviews()` reconciles DOM changes
3. Cards are added/updated/removed based on running processes

## Important Constraints

- Always use `uv` package manager, never pip
- The app auto-refreshes every 2 seconds via WebSocket
- Port detection is limited to prevent showing internal/ephemeral ports
- IDE processes (Code, Git) are intentionally filtered out
- Frontend uses vanilla JavaScript - no React/Vue/frameworks