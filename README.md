# Process Viewer

A real-time process monitoring web application built with Python Flask and Socket.IO.

## Features

- **Real-time Updates**: Process information updates every 2 seconds via WebSocket connection
- **Process Management**: View detailed information about running processes and kill processes
- **Search & Filter**: Search processes by name, PID, or username
- **Sorting**: Sort processes by PID, name, CPU usage, memory usage, status, etc.
- **System Monitoring**: Real-time CPU and memory usage display
- **Process Details**: Click on any process to see detailed information including:
  - Memory usage (RSS/VMS)
  - CPU percentage
  - Thread count
  - Creation time
  - Command line arguments
  - Working directory
  - Environment variables
  - Network connections
  - Open files

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd pyprocess-viewer
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. The application will display all running processes with real-time updates.

## Features Guide

### Searching
- Use the search box to filter processes by name, PID, or username
- Search is case-insensitive and updates in real-time

### Sorting
- Click on any column header to sort by that column
- Use the dropdown menu to quickly sort by common metrics (CPU, Memory, PID, Name)

### Process Actions
- **Details**: Click to view comprehensive information about a process
- **Kill**: Terminate a process (requires appropriate permissions)

### Auto-refresh
- Toggle auto-refresh to pause/resume real-time updates
- Manual refresh available via the Refresh button

## Architecture

- **Backend**: Flask with Socket.IO for real-time communication
- **Process Monitoring**: psutil library for cross-platform process information
- **Frontend**: Vanilla JavaScript with Socket.IO client
- **Styling**: Modern CSS with glassmorphism effects

## Security Notes

- Killing processes requires appropriate system permissions
- The application runs with the permissions of the user who started it
- Be cautious when killing system processes

## Troubleshooting

If you encounter permission errors:
- Run with elevated privileges (use with caution):
  ```bash
  sudo python app.py  # Linux/macOS
  ```
- Or run as Administrator on Windows

## Requirements

- Python 3.7+
- Modern web browser with JavaScript enabled
- Operating System: Windows, macOS, or Linux