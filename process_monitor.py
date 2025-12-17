import psutil
import socket
import time
from typing import List, Dict, Any
import subprocess
import os


class ProcessMonitor:
    """Monitor and manage Python/Node development processes"""

    def __init__(self):
        self.target_processes = ['python', 'python3', 'node', 'npm', 'yarn', 'pnpm', 'deno', 'bun']

    def get_listening_ports(self, pid: int) -> List[int]:
        """Get all ports that a process is listening on"""
        ports = []
        try:
            proc = psutil.Process(pid)
            connections = proc.connections(kind='inet')
            for conn in connections:
                if conn.status == 'LISTEN' or conn.status == psutil.CONN_LISTEN:
                    ports.append(conn.laddr.port)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return sorted(list(set(ports)))

    def get_process_info(self, proc: psutil.Process) -> Dict[str, Any]:
        """Extract relevant information from a process"""
        try:
            with proc.oneshot():
                info = {
                    'pid': proc.pid,
                    'name': proc.name(),
                    'exe': proc.exe() if proc.exe() else 'Unknown',
                    'cmdline': ' '.join(proc.cmdline()),
                    'cpu_percent': proc.cpu_percent(),
                    'memory_mb': proc.memory_info().rss / 1024 / 1024,
                    'memory_percent': proc.memory_percent(),
                    'create_time': proc.create_time(),
                    'status': proc.status(),
                    'ports': self.get_listening_ports(proc.pid),
                    'cwd': proc.cwd() if proc.cwd() else 'Unknown',
                    'username': proc.username()
                }

                # Try to get a more descriptive name
                cmdline = proc.cmdline()
                if cmdline:
                    # For Python scripts, try to get the script name
                    if 'python' in info['name'].lower():
                        for i, arg in enumerate(cmdline):
                            if arg.endswith('.py'):
                                info['script_name'] = os.path.basename(arg)
                                break
                            elif i > 0 and cmdline[i-1] == '-m':
                                info['script_name'] = arg
                                break
                    # For Node scripts
                    elif 'node' in info['name'].lower() or 'npm' in info['name'].lower():
                        for arg in cmdline[1:]:
                            if not arg.startswith('-'):
                                info['script_name'] = os.path.basename(arg)
                                break

                # Calculate uptime
                uptime_seconds = time.time() - info['create_time']
                info['uptime'] = self.format_uptime(uptime_seconds)

                return info
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return None

    def format_uptime(self, seconds: float) -> str:
        """Format uptime in a human-readable way"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        elif seconds < 86400:
            hours = int(seconds/3600)
            minutes = int((seconds%3600)/60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds/86400)
            hours = int((seconds%86400)/3600)
            return f"{days}d {hours}h"

    def get_dev_processes(self) -> List[Dict[str, Any]]:
        """Get all development-related processes"""
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if it's a process we care about
                proc_name = proc.info['name'].lower() if proc.info['name'] else ''

                # Skip if not a target process
                is_target = False
                for target in self.target_processes:
                    if target in proc_name:
                        is_target = True
                        break

                if not is_target:
                    continue

                # Skip system Python processes
                cmdline = proc.info.get('cmdline', [])
                if cmdline:
                    cmdline_str = ' '.join(cmdline).lower()
                    # Skip common system processes
                    skip_patterns = [
                        '/usr/libexec/',
                        'chrome',
                        'electron',
                        'vscode',
                        'code-helper',
                        'microsoft',
                        'dropbox',
                        'slack',
                        'spotify'
                    ]
                    if any(pattern in cmdline_str for pattern in skip_patterns):
                        continue

                # Get detailed info
                info = self.get_process_info(proc)
                if info and (info['ports'] or 'python' in proc_name or 'node' in proc_name):
                    processes.append(info)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by memory usage
        processes.sort(key=lambda x: x['memory_mb'], reverse=True)
        return processes

    def kill_process(self, pid: int) -> Dict[str, Any]:
        """Kill a process by PID"""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.terminate()

            # Wait a bit and force kill if needed
            time.sleep(0.5)
            if proc.is_running():
                proc.kill()

            return {'success': True, 'message': f'Process {pid} ({proc_name}) terminated'}
        except psutil.NoSuchProcess:
            return {'success': False, 'message': f'Process {pid} not found'}
        except psutil.AccessDenied:
            return {'success': False, 'message': f'Access denied to kill process {pid}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}


if __name__ == "__main__":
    # Test the monitor
    monitor = ProcessMonitor()
    processes = monitor.get_dev_processes()

    print(f"Found {len(processes)} development processes:\n")

    for proc in processes:
        print(f"PID: {proc['pid']}")
        print(f"  Name: {proc.get('script_name', proc['name'])}")
        print(f"  Command: {proc['cmdline'][:100]}...")
        print(f"  Ports: {proc['ports']}")
        print(f"  Memory: {proc['memory_mb']:.1f} MB")
        print(f"  CPU: {proc['cpu_percent']:.1f}%")
        print(f"  Uptime: {proc['uptime']}")
        print()