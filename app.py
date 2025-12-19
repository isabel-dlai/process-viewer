from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from process_identifier import ProcessIdentifier
import psutil

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
identifier = ProcessIdentifier()


@app.route('/')
def index():
    """Serve the main interface"""
    return render_template('index.html')


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

        # Performance: Use interval=None for non-blocking CPU check
        # This returns the average CPU usage since last call, not blocking
        system_info = {
            'cpu_percent': psutil.cpu_percent(interval=None),
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


@socketio.on('kill_process_group')
def handle_kill_process_group(data):
    """Kill a process and all its related processes"""
    try:
        import time

        main_pid = data.get('pid')
        related_pids = data.get('related_pids', [])

        killed_pids = []
        failed_pids = []

        # Kill related processes first (children, bundled processes)
        for pid in related_pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                killed_pids.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                failed_pids.append(pid)

        # Give processes a moment to terminate gracefully
        time.sleep(0.5)

        # Force kill any that didn't terminate
        for pid in killed_pids[:]:
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    proc.kill()
            except psutil.NoSuchProcess:
                pass  # Already dead, that's fine

        # Kill main process last
        try:
            main_proc = psutil.Process(main_pid)
            main_proc.terminate()
            time.sleep(0.5)
            if main_proc.is_running():
                main_proc.kill()
            killed_pids.insert(0, main_pid)
        except psutil.NoSuchProcess:
            emit('process_killed', {
                'success': False,
                'error': 'Main process not found',
                'pid': main_pid
            })
            return
        except psutil.AccessDenied:
            emit('process_killed', {
                'success': False,
                'error': 'Access denied',
                'pid': main_pid
            })
            return

        emit('process_group_killed', {
            'success': True,
            'main_pid': main_pid,
            'killed_pids': killed_pids,
            'failed_pids': failed_pids,
            'total_killed': len(killed_pids)
        })

    except Exception as e:
        emit('process_group_killed', {
            'success': False,
            'error': str(e),
            'pid': main_pid
        })


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

    # Initialize CPU monitoring for non-blocking calls
    psutil.cpu_percent(interval=None)

    socketio.run(app, debug=True, port=5555, allow_unsafe_werkzeug=True)