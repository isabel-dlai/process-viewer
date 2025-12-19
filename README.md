# Process Viewer

A real-time dashboard showing live previews of your running dev apps. See what's running, on which port, with thumbnail previews.

## Features

- **Live Previews**: Scaled-down iframe previews of running apps
- **Smart Grouping**: Bundles frontend/backend pairs and related processes (workers, bundlers, package managers)
- **Port Detection**: Shows web-friendly ports (3000-3010, 5000-5010, 8000-8100, etc.)
- **Kill Processes**: Stop apps and their related processes from the UI
- **Real-time Updates**: Refreshes every 2 seconds via WebSocket

Supports Python (Flask, FastAPI, Django, Streamlit, Gradio), Node.js (Express, Next.js, Vite), Ruby (Rails), and Docker containers.

## Quick Start

```bash
# Install
uv add flask flask-socketio flask-cors psutil

# Run
uv run python app.py

# Open http://localhost:5555
```

## Architecture

```
app.py                  # Flask + Socket.IO server
process_identifier.py   # Process detection and categorization
static/js/app.js        # Frontend with DOM reconciliation
static/css/style.css    # Retro terminal theme
templates/              # Jinja2 templates
```

## Requirements

- Python 3.13+
- `uv` package manager

## License

MIT
