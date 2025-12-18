# Process Viewer

A real-time web-based process monitoring application designed for **vibe coders** who juggle multiple local development apps and need a clean, visual way to track what's running, where it's running, and what custom tools they have available.

## Why This Exists

If you're the kind of developer who has:
- Multiple frontend/backend pairs running simultaneously
- That Streamlit data viz tool you built last week still running on port 8501
- A Flask API, a Next.js app, and a Gradio demo all going at once
- No idea which port your drawing app is on
- Too many terminal tabs to keep track of

**This is for you.** Process Viewer gives you a single dashboard with live previews of all your running dev apps, intelligent grouping of related processes, and instant access to the ports and tools you need.

## Features

### 🎯 Smart App Detection & Grouping
- **Live Previews**: See your running apps with live iframe previews right in the dashboard
- **Intelligent Pairing**: Automatically detects and groups frontend/backend pairs (e.g., `/drawing-tutor/frontend` + `/drawing-tutor/backend`)
- **Related Process Bundling**: Groups package managers, build tools, workers, and virtual environments under their parent app
- **Focus on What Matters**: Filters out IDE noise (VS Code, Git) to show only your actual running applications

### 📍 Port & Process Management
- **Port Detection**: Shows only web-friendly ports (3000-3010, 4000-4010, 5000-5010, 8000-8100, etc.)
- **Quick Access**: Click any port badge to open that app in your browser
- **Process Details**: View CPU, memory, working directory, and command-line args
- **Real-time Updates**: Everything updates every 2 seconds via WebSocket

### 🔍 Supported App Types
- **Python**: Flask, FastAPI, Django, Streamlit, Gradio, Uvicorn
- **Node.js**: Express, Next.js, React dev servers, Vite, Webpack
- **Ruby**: Rails, Sinatra
- **Containers**: Docker apps with exposed ports
- **Static Servers**: Any HTTP server on common dev ports

### 🎨 Clean, Organized UI
- **Preview Cards**: Frontend apps displayed prominently with live previews
- **Bundled Processes**: Supporting processes (backends, bundlers, package managers) organized underneath
- **No Iframe Refreshing**: Sophisticated DOM reconciliation keeps your previews stable
- **System Monitoring**: CPU and memory usage at a glance

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd pyprocess-viewer
```

2. Install dependencies using `uv` (never use pip):
```bash
uv init
uv add flask flask-socketio flask-cors psutil python-socketio
```

## Usage

1. Run the application:
```bash
uv run python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5555
```

3. See all your running dev apps with live previews and organized process info!

### Kill all running instances (if needed):
```bash
pkill -f "python app.py"
```

## How It Works

### Two-Pass Grouping Algorithm

**Pass 1: Same-Directory Grouping**
- Merges multiple backend processes in the same directory (e.g., multiple Python workers)
- Prevents duplicate cards for the same service

**Pass 2: Frontend/Backend Pairing**
- Detects frontend/backend pairs across different directories
- Validates common project root (e.g., `/my-app/frontend` and `/my-app/backend`)
- Bundles backend as a related process under the frontend card

### Related Process Detection

Automatically detects and bundles:
- **Package Managers**: UV, npm, yarn, pnpm
- **Build Tools**: Vite, Webpack, esbuild
- **Virtual Environments**: .venv, virtualenv, pipenv
- **Auto-restart Tools**: Nodemon
- **Workers**: Celery, RQ, Huey, Gunicorn/Uvicorn workers

## Architecture

- **Backend**: Flask + Socket.IO for real-time communication
- **Process Intelligence**: Custom categorization engine (580 LOC) for smart app detection
- **Frontend**: Vanilla JavaScript with DOM reconciliation pattern to prevent iframe refreshing
- **Monitoring**: psutil for cross-platform process information
- **Updates**: WebSocket emits 'process_update' events every 2 seconds

### Key Files
- `app.py`: Flask server with Socket.IO handlers
- `process_identifier.py`: Smart process categorization engine
- `process_monitor.py`: System process queries
- `static/js/app.js`: Frontend with iframe persistence logic
- `templates/`: Jinja2 templates

## Use Cases

- **Rapid Prototyping**: Spin up multiple tools and keep track of them all
- **Full-stack Development**: Monitor your frontend, backend, and database tools simultaneously
- **Machine Learning**: Track your Streamlit dashboards, Gradio demos, and training scripts
- **API Development**: See all your running APIs and their ports at a glance
- **Portfolio Projects**: Manage multiple side projects running on your machine

## Requirements

- Python 3.7+
- `uv` package manager
- Modern web browser with JavaScript enabled
- Operating System: macOS, Linux, or Windows

## Contributing

This is a tool built by vibe coders, for vibe coders. PRs welcome!

## License

MIT
