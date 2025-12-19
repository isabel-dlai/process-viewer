# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Process Viewer is a real-time web dashboard that shows live previews of your running dev apps. Built with Flask, Socket.IO, and vanilla JavaScript.

## Commands

```bash
# Install dependencies (always use uv, never pip)
uv add flask flask-socketio flask-cors psutil

# Run the app
uv run python app.py
# Opens at http://localhost:5555

# Kill running instances
pkill -f "python app.py"
```

## Architecture

### Core Files
- **app.py**: Flask server with Socket.IO. Emits `process_update` every 2 seconds.
- **process_identifier.py**: Process categorization engine (~700 LOC). Identifies app types, extracts names, filters ports, detects related processes.
- **static/js/app.js**: Frontend with DOM reconciliation via `previewManager`
- **templates/**: Jinja2 templates (base.html, index.html)

### Key Implementation Details

**Iframe Previews**: 1280x800px scaled to 38% with CSS transforms. Overlay div handles clicks.

**Port Detection** (process_identifier.py:97-115): Filters to web-friendly ranges (3000-3010, 5000-5010, 8000-8100, etc). Excludes ephemeral ports (49000+).

**Process Filtering**: Excludes IDEs (VS Code, Vim), Git operations. Focuses on /Users or /home directories.

**Related Process Detection**: Uses pre-computed lookup (O(N+M) complexity) to find:
- Package managers (UV, npm, yarn, pnpm)
- Bundlers (Vite, Webpack, esbuild)
- Workers (Celery, Gunicorn, Uvicorn children)
- Auto-restart tools (Nodemon)

**Frontend/Backend Pairing**: Groups apps with common project root and `frontend`/`backend` directory names.

## WebSocket Events

- Client sends: `get_processes`, `kill_process`, `kill_process_group`
- Server emits: `process_update`, `process_killed`, `process_group_killed`

## Troubleshooting

**App not showing**: Check port is in allowed ranges. Verify process isn't filtered as IDE/Git.

**Streamlit/Gradio**: Ensure port 8501-8503 or 7860-7861 respectively.

## Constraints

- Always use `uv`, never pip
- Auto-refresh every 2 seconds via WebSocket
- Vanilla JavaScript only (no frameworks)
- IDE/Git processes intentionally filtered out
