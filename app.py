from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from process_monitor import ProcessMonitor
from process_identifier import ProcessIdentifier
import psutil
import json

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
monitor = ProcessMonitor()
identifier = ProcessIdentifier()


@app.route('/')
def index():
    """Serve the main interface"""
    return render_template('index.html')


@app.route('/api/processes')
def get_processes():
    """Get all development processes"""
    try:
        processes = monitor.get_dev_processes()
        return jsonify({'success': True, 'processes': processes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/process/<int:pid>', methods=['DELETE'])
def kill_process(pid):
    """Kill a process by PID"""
    try:
        result = monitor.kill_process(pid)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/process/<int:pid>')
def get_process(pid):
    """Get details for a specific process"""
    try:
        import psutil
        proc = psutil.Process(pid)
        info = monitor.get_process_info(proc)
        if info:
            return jsonify({'success': True, 'process': info})
        else:
            return jsonify({'success': False, 'error': 'Process not found'}), 404
    except psutil.NoSuchProcess:
        return jsonify({'success': False, 'error': 'Process not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_all_processes():
    """Get all system processes with basic info"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent',
                                     'status', 'username', 'num_threads']):
        try:
            info = proc.info
            # Get memory in MB
            memory_info = proc.memory_info()
            info['memory_mb'] = memory_info.rss / 1024 / 1024
            processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


@socketio.on('connect')
def handle_connect():
    print(f'Client connected')
    emit('connected', {'message': 'Connected to process viewer'})


@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected')


@socketio.on('get_processes')
def handle_get_processes(data=None):
    """Send process list to client"""
    try:
        # Check if we want only user processes or all
        show_all = data.get('show_all', False) if data else False

        if show_all:
            processes = identifier.get_all_processes_enhanced()
        else:
            # Default to showing only user-initiated processes
            processes = identifier.get_user_processes()

        system_info = {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent
        }
        emit('process_update', {
            'processes': processes,
            'system_info': system_info
        })
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('kill_process')
def handle_kill_process(data):
    """Kill a process by PID"""
    try:
        pid = data.get('pid')
        proc = psutil.Process(pid)
        proc.terminate()
        emit('process_killed', {'success': True, 'pid': pid})
    except psutil.NoSuchProcess:
        emit('process_killed', {'success': False, 'error': 'Process not found', 'pid': pid})
    except psutil.AccessDenied:
        emit('process_killed', {'success': False, 'error': 'Access denied', 'pid': pid})
    except Exception as e:
        emit('process_killed', {'success': False, 'error': str(e), 'pid': pid})


@socketio.on('get_process_details')
def handle_get_process_details(data):
    """Get detailed info for a specific process"""
    try:
        pid = data.get('pid')
        proc = psutil.Process(pid)

        # Gather detailed info safely
        details = {
            'pid': pid,
            'name': proc.name(),
            'status': proc.status(),
            'username': proc.username(),
            'cpu_percent': proc.cpu_percent(),
            'memory_percent': proc.memory_percent(),
            'memory_info': proc.memory_info()._asdict(),
            'num_threads': proc.num_threads(),
            'create_time': proc.create_time()
        }

        # Try to get additional info, but don't fail if we can't
        try:
            details['exe'] = proc.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            details['exe'] = None

        try:
            details['cwd'] = proc.cwd()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            details['cwd'] = None

        try:
            details['cmdline'] = proc.cmdline()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            details['cmdline'] = []

        try:
            details['connections'] = [conn._asdict() for conn in proc.connections()]
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            details['connections'] = []

        try:
            details['open_files'] = [f._asdict() for f in proc.open_files()]
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            details['open_files'] = []

        emit('process_details', details)
    except psutil.NoSuchProcess:
        emit('error', {'message': 'Process not found'})
    except Exception as e:
        emit('error', {'message': str(e)})


if __name__ == '__main__':
    print("Starting Process Viewer on http://localhost:5555")
    print("Open your browser to view running processes")
    socketio.run(app, debug=True, port=5555, allow_unsafe_werkzeug=True)