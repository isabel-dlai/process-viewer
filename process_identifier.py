"""
Enhanced process identification and categorization
"""
import psutil
import os
import re
import time
from typing import Dict, List, Any, Optional
from pathlib import Path


class ProcessIdentifier:
    """Identify and describe processes in a user-friendly way"""

    def __init__(self, cache_duration=5.0):
        # Performance: Cache process list to avoid scanning all processes every request
        self.cache_duration = cache_duration  # seconds
        self._cached_processes = None
        self._cache_timestamp = 0
        # Common terminal emulators and shells
        self.terminals = {
            'terminal', 'iterm2', 'iterm', 'alacritty', 'kitty', 'wezterm',
            'gnome-terminal', 'konsole', 'xterm', 'tmux', 'screen',
            'bash', 'zsh', 'fish', 'sh', 'tcsh', 'ksh', 'powershell', 'cmd'
        }

        # Known development tools and their descriptions
        self.known_apps = {
            # Package managers
            'uv': 'UV Package Manager - Fast Python package installer',
            'pip': 'Pip - Python package installer',
            'npm': 'NPM - Node.js package manager',
            'yarn': 'Yarn - JavaScript package manager',
            'pnpm': 'PNPM - Fast, disk space efficient package manager',
            'cargo': 'Cargo - Rust package manager',
            'brew': 'Homebrew - macOS package manager',

            # Development servers
            'webpack': 'Webpack Dev Server - JavaScript bundler',
            'vite': 'Vite Dev Server - Fast frontend build tool',
            'next': 'Next.js Dev Server - React framework',
            'django': 'Django Dev Server - Python web framework',
            'flask': 'Flask Dev Server - Python micro framework',
            'rails': 'Rails Server - Ruby web framework',
            'nodemon': 'Nodemon - Node.js auto-restart tool',

            # Databases
            'postgres': 'PostgreSQL Database Server',
            'mysql': 'MySQL Database Server',
            'mongodb': 'MongoDB NoSQL Database',
            'redis': 'Redis In-Memory Data Store',
            'elasticsearch': 'Elasticsearch Search Engine',

            # Tools
            'docker': 'Docker Container Platform',
            'kubectl': 'Kubernetes CLI',
            'terraform': 'Terraform Infrastructure Tool',
            'git': 'Git Version Control',
            'code': 'Visual Studio Code',
            'vim': 'Vim Text Editor',
            'nvim': 'Neovim Text Editor',
            'emacs': 'Emacs Text Editor',
        }

    def identify_process(self, proc: psutil.Process, check_ports=True) -> Dict[str, Any]:
        """Get enhanced information about a process

        Args:
            proc: Process to identify
            check_ports: If False, skip expensive port scanning (default: True)
        """
        try:
            # Use oneshot() context manager for better performance
            with proc.oneshot():
                base_info = {
                    'pid': proc.pid,
                    'name': proc.name(),
                    'cpu_percent': proc.cpu_percent(),
                    'memory_percent': proc.memory_percent(),
                    'memory_mb': proc.memory_info().rss / 1024 / 1024,
                    'status': proc.status(),
                    'username': proc.username(),
                    'num_threads': proc.num_threads(),
                    'create_time': proc.create_time()
                }

            # Get listening ports for this process (can be expensive - make it optional)
            if check_ports:
                try:
                    connections = proc.connections(kind='inet')
                    listening_ports = []
                    for conn in connections:
                        if conn.status == 'LISTEN':
                            port = conn.laddr.port
                            # Filter to only common web/app ports, exclude internal API ports
                            # Common web development port ranges
                            common_web_ports = [
                                80, 443,  # Standard HTTP/HTTPS
                                3000, 3001, 3002, 3003, 3004, 3005,  # React/Node common ports
                                4000, 4001, 4200,  # Angular, Phoenix
                                5000, 5001, 5173, 5174, 5555, 5556,  # Flask, Vite, custom
                                8000, 8001, 8080, 8081, 8888,  # Django, general web
                                8501, 8502, 8503,  # Streamlit
                                9000, 9001, 9090,  # Various frameworks
                                7860, 7861,  # Gradio
                            ]

                            # Include if it's a known web port or in common ranges
                            if port in common_web_ports:
                                listening_ports.append(port)
                            # Also include ports in these ranges that are likely web servers
                            elif (3000 <= port <= 3010) or (4000 <= port <= 4010) or \
                                 (5000 <= port <= 5010) or (7860 <= port <= 7870) or \
                                 (8000 <= port <= 8100) or (8500 <= port <= 8510) or \
                                 (9000 <= port <= 9100):
                                # But exclude known internal/API ports that aren't meant for browser access
                                exclude_ports = {
                                    # Common internal API ports that tools use
                                    49152, 49153, 49154, 49155, 49156, 49157, 49158, 49159,  # Dynamic/private ports
                                    49546, 49547, 49548, 49549, 49550, 49551, 49552,  # More dynamic ports
                                    49571, 49566, 49565, 49562,  # VS Code internal ports
                                    # Add more as needed
                                }
                                if port not in exclude_ports and not (49000 <= port <= 65535):  # Exclude ephemeral port range
                                    listening_ports.append(port)

                    # For the chat-explorer case, prioritize lower port numbers (usually the main server)
                    listening_ports = list(set(listening_ports))  # Remove duplicates
                    listening_ports.sort()  # Sort so main ports appear first

                    base_info['listening_ports'] = listening_ports
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    base_info['listening_ports'] = []
            else:
                # If skipping port check, set empty list
                base_info['listening_ports'] = []

            # Get command line for better identification
            try:
                cmdline = proc.cmdline()
                base_info['cmdline'] = cmdline
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                cmdline = []
                base_info['cmdline'] = []

            # Get parent process info for context
            try:
                parent = proc.parent()
                if parent:
                    base_info['parent_pid'] = parent.pid
                    base_info['parent_name'] = parent.name()
                    # Check if launched from terminal
                    base_info['from_terminal'] = self._is_from_terminal(proc, parent)
                else:
                    base_info['parent_pid'] = None
                    base_info['parent_name'] = None
                    base_info['from_terminal'] = False
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                base_info['parent_pid'] = None
                base_info['parent_name'] = None
                base_info['from_terminal'] = False

            # Get enhanced description
            description = self._get_process_description(proc, cmdline)
            base_info['description'] = description['description']
            base_info['app_name'] = description['app_name']
            base_info['category'] = description['category']
            base_info['is_user_process'] = description['is_user_process']

            # Get working directory for context
            try:
                cwd = proc.cwd()
                base_info['cwd'] = cwd
                # Check if it's in a user directory
                if cwd and ('/Users/' in cwd or '/home/' in cwd):
                    base_info['in_user_directory'] = True
                else:
                    base_info['in_user_directory'] = False
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                base_info['cwd'] = None
                base_info['in_user_directory'] = False

            return base_info

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def _is_from_terminal(self, proc: psutil.Process, parent: psutil.Process) -> bool:
        """Check if process was launched from a terminal"""
        try:
            # Check immediate parent
            if parent and parent.name().lower() in self.terminals:
                return True

            # Check grandparent
            grandparent = parent.parent() if parent else None
            if grandparent and grandparent.name().lower() in self.terminals:
                return True

            # Check if process itself is a shell script or command
            cmdline = proc.cmdline()
            if cmdline and len(cmdline) > 0:
                # Check for common shell invocations
                if any(shell in cmdline[0].lower() for shell in ['bash', 'zsh', 'sh', 'python', 'node', 'ruby']):
                    return True

        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

        return False

    def _get_process_description(self, proc: psutil.Process, cmdline: List[str]) -> Dict[str, str]:
        """Generate a user-friendly description of the process"""
        result = {
            'description': proc.name(),
            'app_name': proc.name(),
            'category': 'System',
            'is_user_process': False
        }

        proc_name_lower = proc.name().lower()

        # Check if it's a known application
        for app, desc in self.known_apps.items():
            if app in proc_name_lower:
                result['description'] = desc
                result['app_name'] = app.title()
                result['category'] = 'Development Tool'
                result['is_user_process'] = True
                return result

        # Analyze command line for better identification
        if cmdline and len(cmdline) > 0:
            cmd = ' '.join(cmdline)

            # Python processes
            if 'python' in proc_name_lower or 'python' in cmd.lower():
                result['category'] = 'Python Application'
                result['is_user_process'] = True

                # Look for the actual script name
                for arg in cmdline:
                    if arg.endswith('.py'):
                        script_path = arg
                        script_name = os.path.basename(arg).replace('.py', '')
                        result['app_name'] = script_name

                        # Get the directory context for better identification
                        try:
                            cwd = proc.cwd()
                            # Extract project/folder name from working directory
                            if cwd:
                                project_name = os.path.basename(cwd)
                                if project_name and project_name != script_name:
                                    context = f" ({project_name})"
                                else:
                                    # Try parent directory
                                    parent_dir = os.path.basename(os.path.dirname(cwd))
                                    if parent_dir and parent_dir not in ['Users', 'home', '']:
                                        context = f" ({parent_dir})"
                                    else:
                                        context = ""
                            else:
                                context = ""
                        except:
                            context = ""

                        # Special cases with context
                        if 'app.py' in arg:
                            result['description'] = f"Flask/Web App: {script_name}{context}"
                        elif 'manage.py' in arg:
                            result['description'] = f"Django App: {script_name}{context}"
                        elif 'setup.py' in arg:
                            result['description'] = f"Python Setup: {script_name}{context}"
                        elif 'server' in script_name.lower():
                            result['description'] = f"Python Server: {script_name}{context}"
                        elif 'api' in script_name.lower():
                            result['description'] = f"API Server: {script_name}{context}"
                        elif 'main' in script_name.lower():
                            result['description'] = f"Main App: {script_name}{context}"
                        elif 'test' in script_name.lower():
                            result['description'] = f"Test Runner: {script_name}{context}"
                        elif 'worker' in script_name.lower():
                            result['description'] = f"Worker Process: {script_name}{context}"
                        else:
                            # Include full path if it's in a meaningful location
                            if '/Users/' in script_path or '/home/' in script_path:
                                # Get relative path from user directory
                                path_parts = script_path.split('/')
                                if 'Documents' in path_parts:
                                    idx = path_parts.index('Documents')
                                    relative_path = '/'.join(path_parts[idx:])
                                    result['description'] = f"Python: {relative_path}"
                                elif 'GitHub' in path_parts:
                                    idx = path_parts.index('GitHub')
                                    relative_path = '/'.join(path_parts[idx:])
                                    result['description'] = f"Python: {relative_path}"
                                elif 'Projects' in path_parts:
                                    idx = path_parts.index('Projects')
                                    relative_path = '/'.join(path_parts[idx:])
                                    result['description'] = f"Python: {relative_path}"
                                else:
                                    result['description'] = f"Python: {script_name}{context}"
                            else:
                                result['description'] = f"Python: {script_name}{context}"
                        break

                # Check for module execution
                if '-m' in cmdline:
                    try:
                        idx = cmdline.index('-m')
                        if idx + 1 < len(cmdline):
                            module = cmdline[idx + 1]
                            result['app_name'] = module

                            # Get context from working directory
                            try:
                                cwd = proc.cwd()
                                if cwd:
                                    project = os.path.basename(cwd)
                                    if project and project not in ['Users', 'home', '']:
                                        context = f" in {project}"
                                    else:
                                        context = ""
                                else:
                                    context = ""
                            except:
                                context = ""

                            # Common Python modules with better descriptions
                            if module == 'http.server':
                                result['description'] = f"Python HTTP Server{context}"
                            elif module == 'flask':
                                result['description'] = f"Flask Dev Server{context}"
                            elif module == 'django':
                                result['description'] = f"Django Server{context}"
                            elif module == 'pytest':
                                result['description'] = f"PyTest Runner{context}"
                            elif module == 'unittest':
                                result['description'] = f"Unit Tests{context}"
                            elif module == 'pip':
                                result['description'] = f"Pip Package Manager{context}"
                            elif module == 'venv':
                                result['description'] = f"Virtual Environment{context}"
                            elif module == 'jupyter':
                                result['description'] = f"Jupyter Notebook{context}"
                            elif module == 'ipython':
                                result['description'] = f"IPython Shell{context}"
                            else:
                                result['description'] = f"Python Module: {module}{context}"
                    except (ValueError, IndexError):
                        pass

                # Check for Streamlit specifically
                if 'streamlit' in cmd.lower():
                    result['app_name'] = 'Streamlit'
                    result['category'] = 'Python Application'
                    # Find the script name
                    for arg in cmdline:
                        if arg.endswith('.py') and 'streamlit' not in arg.lower():
                            script = os.path.basename(arg).replace('.py', '')
                            result['description'] = f"Streamlit App: {script}"
                            break
                    else:
                        result['description'] = "Streamlit Application"

                # Check for virtual environment
                if '.venv' in cmd or 'virtualenv' in cmd or 'pipenv' in cmd:
                    result['description'] += " (Virtual Environment)"

            # Node.js processes
            elif 'node' in proc_name_lower or 'node' in cmd.lower():
                result['category'] = 'Node.js Application'
                result['is_user_process'] = True

                # Get working directory context
                try:
                    cwd = proc.cwd()
                    if cwd:
                        project_name = os.path.basename(cwd)
                        if not project_name or project_name in ['node', 'src', 'dist']:
                            project_name = os.path.basename(os.path.dirname(cwd))
                        context = f" ({project_name})" if project_name and project_name not in ['Users', 'home', ''] else ""
                    else:
                        context = ""
                except:
                    context = ""

                for arg in cmdline:
                    if arg.endswith('.js') or arg.endswith('.ts'):
                        script_path = arg
                        script_name = os.path.basename(arg).replace('.js', '').replace('.ts', '')
                        result['app_name'] = script_name

                        # Special cases with context
                        if 'server' in script_name.lower():
                            result['description'] = f"Node Server: {script_name}{context}"
                        elif 'index' in script_name.lower():
                            result['description'] = f"Node App: {script_name}{context}"
                        elif 'api' in script_name.lower():
                            result['description'] = f"Node API: {script_name}{context}"
                        elif 'worker' in script_name.lower():
                            result['description'] = f"Node Worker: {script_name}{context}"
                        else:
                            # Include path context
                            if '/Users/' in script_path or '/home/' in script_path:
                                path_parts = script_path.split('/')
                                if 'node_modules' in path_parts:
                                    # It's a package being run
                                    result['description'] = f"Node Package: {script_name}{context}"
                                elif any(folder in path_parts for folder in ['Documents', 'GitHub', 'Projects']):
                                    # Show relative path from known folder
                                    for folder in ['Documents', 'GitHub', 'Projects']:
                                        if folder in path_parts:
                                            idx = path_parts.index(folder)
                                            relative_path = '/'.join(path_parts[idx:])
                                            result['description'] = f"Node: {relative_path}"
                                            break
                                else:
                                    result['description'] = f"Node: {script_name}{context}"
                            else:
                                result['description'] = f"Node: {script_name}{context}"
                        break

                # Check for npm scripts
                if 'npm' in cmd and 'run' in cmd:
                    parts = cmd.split('run')
                    if len(parts) > 1:
                        script = parts[1].strip().split()[0] if parts[1].strip() else ''
                        if script:
                            result['app_name'] = f"npm:{script}"
                            result['description'] = f"NPM Script: {script}"

            # Ruby processes
            elif 'ruby' in proc_name_lower or 'ruby' in cmd.lower():
                result['category'] = 'Ruby Application'
                result['is_user_process'] = True

                if 'rails' in cmd:
                    result['app_name'] = 'Rails Server'
                    result['description'] = 'Ruby on Rails Application'
                elif 'bundle' in cmd:
                    result['app_name'] = 'Bundler'
                    result['description'] = 'Ruby Bundler Process'
                else:
                    for arg in cmdline:
                        if arg.endswith('.rb'):
                            script_name = os.path.basename(arg).replace('.rb', '')
                            result['app_name'] = script_name
                            result['description'] = f"Ruby Script: {script_name}"
                            break

            # Docker containers
            elif 'docker' in cmd.lower():
                result['category'] = 'Container'
                result['is_user_process'] = True
                result['app_name'] = 'Docker'

                if 'run' in cmd:
                    # Try to extract container image name
                    parts = cmd.split()
                    for i, part in enumerate(parts):
                        if part == 'run' and i + 1 < len(parts):
                            for j in range(i + 1, len(parts)):
                                if not parts[j].startswith('-'):
                                    image = parts[j].split('/')[-1].split(':')[0]
                                    result['app_name'] = f"Docker: {image}"
                                    result['description'] = f"Docker Container: {image}"
                                    break

            # Git operations
            elif 'git' in cmd.lower():
                result['category'] = 'Version Control'
                result['is_user_process'] = True
                result['app_name'] = 'Git'

                # Identify git operation
                operations = ['clone', 'pull', 'push', 'fetch', 'merge', 'rebase', 'commit']
                for op in operations:
                    if op in cmd:
                        result['description'] = f"Git: {op} operation"
                        break
                else:
                    result['description'] = 'Git Operation'

            # Database processes
            elif any(db in cmd.lower() for db in ['postgres', 'mysql', 'mongodb', 'redis']):
                result['category'] = 'Database'
                result['is_user_process'] = True

                if 'postgres' in cmd.lower():
                    result['app_name'] = 'PostgreSQL'
                    result['description'] = 'PostgreSQL Database Process'
                elif 'mysql' in cmd.lower():
                    result['app_name'] = 'MySQL'
                    result['description'] = 'MySQL Database Process'
                elif 'mongodb' in cmd.lower() or 'mongod' in cmd.lower():
                    result['app_name'] = 'MongoDB'
                    result['description'] = 'MongoDB Database Process'
                elif 'redis' in cmd.lower():
                    result['app_name'] = 'Redis'
                    result['description'] = 'Redis Server Process'

            # IDE/Editor processes
            elif any(ide in cmd.lower() for ide in ['code', 'vscode', 'vim', 'nvim', 'emacs', 'sublime', 'atom']):
                result['category'] = 'Development IDE'
                result['is_user_process'] = True

                if 'code' in cmd.lower() or 'vscode' in cmd.lower():
                    result['app_name'] = 'VS Code'
                    result['description'] = 'Visual Studio Code'
                elif 'vim' in cmd.lower():
                    result['app_name'] = 'Vim'
                    result['description'] = 'Vim Text Editor'
                elif 'nvim' in cmd.lower():
                    result['app_name'] = 'Neovim'
                    result['description'] = 'Neovim Text Editor'
                elif 'emacs' in cmd.lower():
                    result['app_name'] = 'Emacs'
                    result['description'] = 'Emacs Text Editor'

        # Check if it's a user process based on location
        try:
            cwd = proc.cwd()
            if cwd and ('/Users/' in cwd or '/home/' in cwd):
                result['is_user_process'] = True
                if result['category'] == 'System':
                    result['category'] = 'User Process'
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

        return result

    def _find_related_processes(self, main_proc_info: Dict[str, Any], all_procs: List[psutil.Process]) -> List[Dict[str, Any]]:
        """Find processes that are related to the main process (helper processes, package managers, etc.)"""
        related = []
        main_pid = main_proc_info['pid']
        main_cwd = main_proc_info.get('cwd', '')

        for proc in all_procs:
            try:
                if proc.pid == main_pid:
                    continue

                # Get basic info
                cmdline = proc.cmdline()
                cmd_str = ' '.join(cmdline).lower() if cmdline else ''
                proc_name = proc.name().lower()

                # Check if it's a parent/child relationship
                parent = proc.parent()
                is_child = parent and parent.pid == main_pid
                is_parent = main_proc_info.get('parent_pid') == proc.pid

                # Check if same working directory
                try:
                    proc_cwd = proc.cwd()
                    same_cwd = main_cwd and proc_cwd == main_cwd
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    proc_cwd = None
                    same_cwd = False

                # Identify related process types
                related_type = None

                # UV package manager
                if 'uv' in proc_name and same_cwd:
                    related_type = 'Package Manager (UV)'
                # Virtual environment
                elif ('.venv' in cmd_str or 'virtualenv' in cmd_str or 'pipenv' in cmd_str) and same_cwd:
                    related_type = 'Virtual Environment'
                # NPM dev scripts
                elif 'npm' in cmd_str and ('run' in cmd_str or 'dev' in cmd_str) and same_cwd:
                    related_type = 'NPM Script'
                # Node package managers
                elif ('yarn' in proc_name or 'pnpm' in proc_name) and same_cwd:
                    related_type = f'Package Manager ({proc_name.upper()})'
                # Webpack/bundlers
                elif ('webpack' in cmd_str or 'vite' in cmd_str or 'esbuild' in cmd_str) and same_cwd:
                    if 'webpack' in cmd_str:
                        related_type = 'Bundler (Webpack)'
                    elif 'vite' in cmd_str:
                        related_type = 'Bundler (Vite)'
                    else:
                        related_type = 'Bundler (esbuild)'
                # Nodemon
                elif 'nodemon' in cmd_str and same_cwd:
                    related_type = 'Auto-restart (Nodemon)'
                # Python workers or helper processes
                elif is_child and 'python' in proc_name:
                    # Check if it's a worker process
                    if any(keyword in cmd_str for keyword in ['worker', 'celery', 'rq', 'huey']):
                        related_type = 'Worker Process'
                # Gunicorn/Uvicorn workers
                elif is_child and ('gunicorn' in cmd_str or 'uvicorn' in cmd_str):
                    related_type = 'Web Server Worker'

                if related_type:
                    related.append({
                        'pid': proc.pid,
                        'name': proc.name(),
                        'type': related_type,
                        'cpu_percent': proc.cpu_percent(),
                        'memory_mb': proc.memory_info().rss / 1024 / 1024,
                        'cmdline': cmdline[:3] if cmdline else []  # First 3 args for brevity
                    })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return related

    def get_user_processes(self) -> List[Dict[str, Any]]:
        """Get all processes that are likely user-initiated, excluding system processes

        Uses caching to avoid expensive scans on every request.
        """
        # Check cache first
        current_time = time.time()
        if self._cached_processes is not None and (current_time - self._cache_timestamp) < self.cache_duration:
            return self._cached_processes

        processes = []

        # Performance: Quick filter of process names before expensive operations
        # This reduces the number of identify_process() calls significantly
        excluded_names = {'code', 'git', 'vim', 'nvim', 'emacs', 'sublime', 'atom',
                         'code-helper', 'chrome', 'firefox', 'safari', 'slack', 'spotify',
                         'finder', 'dock', 'systemuiserver', 'windowserver'}

        # First pass: Quick filter and collect candidate processes
        candidate_procs = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name_lower = proc.info['name'].lower() if proc.info['name'] else ''

                # Skip obviously excluded processes early
                if any(excluded in proc_name_lower for excluded in excluded_names):
                    continue

                # Skip system processes (most start with these paths)
                try:
                    exe = proc.exe()
                    if exe and ('/System/' in exe or '/usr/libexec/' in exe or '/usr/sbin/' in exe):
                        continue
                except:
                    pass

                candidate_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Second pass: Identify only candidate processes
        for proc in candidate_procs:
            try:
                # Only check ports for processes that might be servers
                # This is a huge performance win
                proc_name = proc.name().lower() if hasattr(proc, 'name') else ''
                might_have_ports = any(keyword in proc_name for keyword in
                                      ['python', 'node', 'npm', 'flask', 'django', 'uvicorn',
                                       'gunicorn', 'streamlit', 'gradio', 'vite', 'webpack'])

                info = self.identify_process(proc, check_ports=might_have_ports)
                if info:
                    # Filter out system processes and unwanted categories
                    if info['category'] in ['System', 'User Process', 'Development IDE']:
                        continue

                    # Also filter out specific apps we don't want to show
                    app_name_lower = info['app_name'].lower()
                    if app_name_lower in ['code', 'git', 'vim', 'nvim', 'emacs', 'sublime', 'atom']:
                        continue

                    # Filter out VS Code related processes
                    if 'visual studio code' in info['description'].lower():
                        continue

                    # Filter out Git operations unless they're long-running servers
                    if app_name_lower == 'git' or 'git version control' in info['description'].lower():
                        continue

                    # Find related/bundled processes
                    info['related_processes'] = self._find_related_processes(info, candidate_procs)

                    processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Update cache
        self._cached_processes = processes
        self._cache_timestamp = current_time

        return processes

    def get_all_processes_enhanced(self) -> List[Dict[str, Any]]:
        """Get more processes with enhanced identification, but still excluding pure system processes"""
        processes = []

        # First pass: collect all process objects for relationship detection
        all_procs = list(psutil.process_iter())

        for proc in all_procs:
            try:
                info = self.identify_process(proc)
                if info:
                    # Exclude system processes and unwanted categories
                    if info['category'] in ['System', 'User Process', 'Development IDE']:
                        # For "Show more", include some system processes if they're recognizable apps
                        if info['category'] == 'System' and any(known in info['name'].lower()
                                                                  for known in ['docker', 'postgres', 'mysql',
                                                                               'redis', 'mongo', 'elastic']):
                            # Find related processes for these too
                            info['related_processes'] = self._find_related_processes(info, all_procs)
                            processes.append(info)
                        continue

                    # Also filter out IDEs and Git even in "show more"
                    app_name_lower = info['app_name'].lower()
                    if app_name_lower in ['code', 'git', 'vim', 'nvim', 'emacs', 'sublime', 'atom']:
                        continue

                    if 'visual studio code' in info['description'].lower():
                        continue

                    if app_name_lower == 'git' or 'git version control' in info['description'].lower():
                        continue

                    # Find related/bundled processes
                    info['related_processes'] = self._find_related_processes(info, all_procs)

                    processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes