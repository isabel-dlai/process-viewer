// Initialize Socket.IO connection
const socket = io();

// Global variables
let processes = [];
let sortBy = 'cpu';
let sortOrder = 'desc';
let autoRefresh = true;

// Preview Manager - persistent state for all app preview cards
const previewManager = {
    // Map of card ID -> DOM element (entire card)
    cards: new Map(),

    // Track current state to detect changes
    currentGroups: [],

    // Get a unique ID for a group or single app
    getGroupId(group) {
        if (group.type === 'group') {
            return `group-${group.frontend?.pid || ''}-${group.backend?.pid || ''}`;
        } else {
            return `single-${group.app.pid}-${group.app.listening_ports[0]}`;
        }
    },

    // Clear all cards (for complete reset)
    clear() {
        this.cards.clear();
        this.currentGroups = [];
    }
};

// DOM elements
const previewGrid = document.getElementById('app-preview-grid');

// Terminal-style console logging
function terminalLog(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
    const prefix = type === 'error' ? '[ERR]' : type === 'warn' ? '[WRN]' : '[SYS]';
    console.log(`%c${timestamp} ${prefix} ${message}`, `color: ${type === 'error' ? '#ff0055' : type === 'warn' ? '#ffff00' : '#00ff41'}; font-family: monospace;`);
}

// Socket.IO event listeners
socket.on('connect', () => {
    terminalLog('WEBSOCKET CONNECTION ESTABLISHED');
    terminalLog('INITIATING PROCESS SCAN...', 'info');
    requestProcesses();
});

socket.on('process_update', (data) => {
    processes = data.processes;
    updateSystemInfo(data.system_info);
    renderAppPreviews();

    // Log process count updates
    const activeApps = processes.filter(p => p.listening_ports && p.listening_ports.length > 0).length;
    if (activeApps > 0) {
        terminalLog(`DETECTED ${activeApps} ACTIVE PROCESS${activeApps > 1 ? 'ES' : ''} WITH PORTS`);
    }
});

// Kill functionality removed for safety
// socket.on('process_killed', (data) => {
//     if (data.success) {
//         alert(`Process ${data.pid} killed successfully`);
//         requestProcesses();
//     } else {
//         alert(`Failed to kill process: ${data.error}`);
//     }
// });

// Process details modal removed

// Event listeners removed - no controls needed for preview-only view

// Functions
function requestProcesses() {
    socket.emit('get_processes', { show_all: false });
}

// Render app preview cards for processes with ports
// Uses reconciliation to update only what changed, preserving iframes
function renderAppPreviews() {
    const previewGrid = document.getElementById('app-preview-grid');
    const previewSection = document.getElementById('app-preview-section');

    // Filter processes that have ports
    const appsWithPorts = processes.filter(proc =>
        proc.listening_ports && proc.listening_ports.length > 0
    );

    // Group related apps (frontend/backend pairs)
    const appGroups = groupRelatedApps(appsWithPorts);

    if (appGroups.length === 0) {
        previewSection.classList.add('hidden');
        // Clean up all cards when no apps are running
        previewManager.cards.clear();
        previewGrid.innerHTML = '';
        return;
    } else {
        previewSection.classList.remove('hidden');
    }

    // Reconciliation: compare new groups with existing cards
    const newGroupIds = new Set(appGroups.map(g => previewManager.getGroupId(g)));
    const existingGroupIds = new Set(previewManager.cards.keys());

    // Remove cards that no longer exist
    for (const groupId of existingGroupIds) {
        if (!newGroupIds.has(groupId)) {
            const card = previewManager.cards.get(groupId);
            if (card && card.parentNode) {
                card.remove();
            }
            previewManager.cards.delete(groupId);
        }
    }

    // Add or update cards
    appGroups.forEach((group, index) => {
        const groupId = previewManager.getGroupId(group);

        if (previewManager.cards.has(groupId)) {
            // Card exists - update only the non-iframe parts
            const card = previewManager.cards.get(groupId);
            updateAppCard(card, group);

            // Ensure correct position in grid
            const currentIndex = Array.from(previewGrid.children).indexOf(card);
            if (currentIndex !== index) {
                if (index >= previewGrid.children.length) {
                    previewGrid.appendChild(card);
                } else {
                    previewGrid.insertBefore(card, previewGrid.children[index]);
                }
            }
        } else {
            // Card doesn't exist - create it
            const card = createAppCard(group);
            previewManager.cards.set(groupId, card);

            // Insert at correct position
            if (index >= previewGrid.children.length) {
                previewGrid.appendChild(card);
            } else {
                previewGrid.insertBefore(card, previewGrid.children[index]);
            }
        }
    });
}

// Helper function to check if app is frontend
function isFrontendApp(app) {
    return app.listening_ports.some(port =>
        [3000, 3001, 5173, 5174, 4200].includes(port)
    );
}

// Helper function to check if app is backend
function isBackendApp(app) {
    return app.listening_ports.some(port =>
        [8000, 8001, 5000, 5001, 4000, 4001, 8080].includes(port) ||
        (port >= 8080 && port <= 8090)
    );
}

// Helper function to get common path root
function getCommonRoot(path1, path2) {
    if (!path1 || !path2) return null;

    const parts1 = path1.split('/');
    const parts2 = path2.split('/');

    const common = [];
    for (let i = 0; i < Math.min(parts1.length, parts2.length); i++) {
        if (parts1[i] === parts2[i]) {
            common.push(parts1[i]);
        } else {
            break;
        }
    }

    return common.length >= 5 ? common.join('/') : null; // At least /Users/name/Documents/GitHub/project
}

// Check if paths indicate frontend/backend structure
function areFrontendBackendPair(frontendPath, backendPath) {
    const commonRoot = getCommonRoot(frontendPath, backendPath);
    if (!commonRoot) return false;

    // Check if one path contains 'frontend' and the other 'backend'
    const fe_has_frontend = frontendPath.toLowerCase().includes('frontend');
    const be_has_backend = backendPath.toLowerCase().includes('backend');

    return fe_has_frontend && be_has_backend;
}

// Group related frontend and backend apps
function groupRelatedApps(apps) {
    const groups = [];
    const used = new Set();

    // First pass: group apps in the same directory
    apps.forEach(app => {
        if (used.has(app.pid)) return;

        // Find apps in the exact same directory
        const relatedApps = apps.filter(other => {
            if (other.pid === app.pid || used.has(other.pid)) return false;
            if (app.cwd && other.cwd) {
                return app.cwd === other.cwd;
            }
            return false;
        });

        // Only create a group if we have multiple apps WITH PORTS
        const appsWithPorts = [app, ...relatedApps].filter(a => a.listening_ports && a.listening_ports.length > 0);

        if (relatedApps.length > 0 && appsWithPorts.length > 1) {
            // Multiple backend processes in same directory - merge them
            // Use the first one as primary, add others to its related_processes
            const primaryApp = app;

            // Add all other apps as related processes
            relatedApps.forEach(other => {
                if (other.listening_ports && other.listening_ports.length > 0) {
                    // This is another backend with ports - add it as a related process
                    if (!primaryApp.related_processes) {
                        primaryApp.related_processes = [];
                    }
                    primaryApp.related_processes.push({
                        pid: other.pid,
                        name: other.app_name || other.name,
                        type: 'Backend Instance',
                        cpu_percent: other.cpu_percent || 0,
                        memory_mb: other.memory_mb || 0,
                        cmdline: other.cmdline ? other.cmdline.slice(0, 3) : [],
                        ports: other.listening_ports || []
                    });

                    // Also merge its related processes
                    if (other.related_processes && other.related_processes.length > 0) {
                        primaryApp.related_processes.push(...other.related_processes);
                    }
                }
                used.add(other.pid);
            });

            // Treat primary app as single
            const isFrontend = isFrontendApp(primaryApp);
            const isBackend = isBackendApp(primaryApp);

            groups.push({
                type: 'single',
                app: primaryApp,
                appType: isFrontend ? 'frontend' : (isBackend ? 'backend' : 'fullstack')
            });
            used.add(primaryApp.pid);
        } else {
            // Single app (will be handled in second pass)
            const isFrontend = isFrontendApp(app);
            const isBackend = isBackendApp(app);

            groups.push({
                type: 'single',
                app: app,
                appType: isFrontend ? 'frontend' : (isBackend ? 'backend' : 'fullstack')
            });
            used.add(app.pid);
        }
    });

    // Second pass: try to pair frontends with backends from different directories
    // Instead of creating a group, add backend as a bundled process to frontend
    const singleGroups = groups.filter(g => g.type === 'single');
    const frontends = singleGroups.filter(g => g.appType === 'frontend');
    const backends = singleGroups.filter(g => g.appType === 'backend');

    frontends.forEach(feGroup => {
        const fe = feGroup.app;

        // Find matching backends
        for (let beGroup of backends) {
            const be = beGroup.app;

            // Check if they share a common project root and have frontend/backend structure
            if (areFrontendBackendPair(fe.cwd, be.cwd)) {
                // Add backend as a bundled process to the frontend
                if (!fe.related_processes) {
                    fe.related_processes = [];
                }

                // Add the backend app as a bundled process
                fe.related_processes.push({
                    pid: be.pid,
                    name: be.app_name || be.name,
                    type: 'Backend Server',
                    cpu_percent: be.cpu_percent || 0,
                    memory_mb: be.memory_mb || 0,
                    cmdline: be.cmdline ? be.cmdline.slice(0, 3) : [],
                    ports: be.listening_ports || []
                });

                // Also add any related processes from the backend
                if (be.related_processes && be.related_processes.length > 0) {
                    fe.related_processes.push(...be.related_processes);
                }

                // Remove the backend from groups since it's now bundled with frontend
                const beIndex = groups.indexOf(beGroup);
                if (beIndex !== -1) {
                    groups.splice(beIndex, 1);
                }

                break; // Only pair with one backend
            }
        }
    });

    return groups;
}

// Get project name from path
function getProjectName(app) {
    if (app.cwd) {
        const parts = app.cwd.split('/');
        // Get the last meaningful directory name
        let projectName = parts[parts.length - 1] || parts[parts.length - 2] || 'Project';

        // Convert directory name to readable format
        // e.g., "drawing-tutor" => "Drawing Tutor", "myApp" => "My App"
        projectName = projectName
            .replace(/[-_]/g, ' ')  // Replace hyphens and underscores with spaces
            .replace(/([a-z])([A-Z])/g, '$1 $2')  // Add space between camelCase
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');

        return projectName;
    }
    return app.app_name || 'Application';
}

// Update existing app card without recreating iframes
function updateAppCard(card, group) {
    if (group.type === 'group') {
        // Update group card title and info (non-iframe parts only)
        const titleElement = card.querySelector('.app-group-title');
        if (titleElement) {
            titleElement.textContent = group.name;
        }

        // Update related processes section for grouped apps
        const allRelatedProcesses = [];
        if (group.frontend && group.frontend.related_processes) {
            allRelatedProcesses.push(...group.frontend.related_processes);
        }
        if (group.backend && group.backend.related_processes) {
            allRelatedProcesses.push(...group.backend.related_processes);
        }

        const uniqueRelated = allRelatedProcesses.filter((proc, index, self) =>
            index === self.findIndex(p => p.pid === proc.pid)
        );

        updateRelatedProcessesSection(card, uniqueRelated);
        // Note: iframes remain untouched, they persist in their containers
    } else {
        // Update single app card
        const app = group.app;
        const projectName = getProjectName(app);

        // Update name
        const nameElement = card.querySelector('.app-card-name');
        if (nameElement) {
            nameElement.textContent = projectName;
        }

        // Update port link
        const port = app.listening_ports[0];
        const url = `http://localhost:${port}`;
        const portLink = card.querySelector('.app-card-port');
        if (portLink) {
            portLink.href = url;
            portLink.textContent = `:${port}`;
        }

        // Update description
        const desc = card.querySelector('.app-card-info span:not(.app-card-type)');
        if (desc) {
            desc.textContent = app.description;
        }

        // Update type
        const typeElement = card.querySelector('.app-card-type');
        if (typeElement) {
            typeElement.className = `app-card-type type-${group.appType}`;
            typeElement.textContent = group.appType;
        }

        // Update footer links
        const openBtn = card.querySelector('.app-action.primary');
        if (openBtn) {
            openBtn.href = url;
        }

        // Update related processes section
        updateRelatedProcessesSection(card, app.related_processes);

        // Note: iframe is not touched - it remains in the preview container
    }
}

// Update or create related processes section in a card
function updateRelatedProcessesSection(card, relatedProcesses) {
    const existingSection = card.querySelector('.related-processes');

    if (!relatedProcesses || relatedProcesses.length === 0) {
        // Remove existing section if no related processes
        if (existingSection) {
            existingSection.remove();
        }
        return;
    }

    if (existingSection) {
        // Update existing section
        existingSection.remove();
    }

    // Create new section
    const newSection = createRelatedProcessesSection(relatedProcesses);
    if (newSection) {
        card.appendChild(newSection);
    }
}

// Create app preview card
function createAppCard(group) {
    const card = document.createElement('div');

    if (group.type === 'group') {
        // Create grouped app card with toggle
        card.className = 'app-group';

        // Create unique ID for this group
        const groupId = `group-${group.frontend?.pid || ''}-${group.backend?.pid || ''}`;
        card.setAttribute('data-group-id', groupId);

        // Header with toggle buttons
        const header = document.createElement('div');
        header.className = 'app-group-header';

        const headerTitle = document.createElement('span');
        headerTitle.className = 'app-group-title';
        headerTitle.textContent = group.name;

        const toggleButtons = document.createElement('div');
        toggleButtons.className = 'app-toggle-buttons';

        if (group.frontend && group.backend) {
            const frontendBtn = document.createElement('button');
            frontendBtn.className = 'toggle-btn active';
            frontendBtn.textContent = 'Frontend';
            frontendBtn.setAttribute('data-view', 'frontend');

            const backendBtn = document.createElement('button');
            backendBtn.className = 'toggle-btn';
            backendBtn.textContent = 'Backend';
            backendBtn.setAttribute('data-view', 'backend');

            frontendBtn.onclick = () => toggleView(groupId, 'frontend');
            backendBtn.onclick = () => toggleView(groupId, 'backend');

            toggleButtons.appendChild(frontendBtn);
            toggleButtons.appendChild(backendBtn);
        }

        header.appendChild(headerTitle);
        header.appendChild(toggleButtons);
        card.appendChild(header);

        // Content area with both views
        const content = document.createElement('div');
        content.className = 'app-group-content';

        if (group.frontend) {
            const frontendView = createSingleAppElement(group.frontend, 'Frontend', groupId);
            frontendView.classList.add('app-view', 'active');
            frontendView.setAttribute('data-view-type', 'frontend');
            content.appendChild(frontendView);
        }

        if (group.backend) {
            const backendView = createSingleAppElement(group.backend, 'Backend', groupId);
            backendView.classList.add('app-view');
            if (!group.frontend) backendView.classList.add('active');
            backendView.setAttribute('data-view-type', 'backend');
            backendView.style.display = group.frontend ? 'none' : 'block';
            content.appendChild(backendView);
        }

        card.appendChild(content);

        // Add related processes section for grouped apps
        // Combine related processes from both frontend and backend
        const allRelatedProcesses = [];
        if (group.frontend && group.frontend.related_processes) {
            allRelatedProcesses.push(...group.frontend.related_processes);
        }
        if (group.backend && group.backend.related_processes) {
            allRelatedProcesses.push(...group.backend.related_processes);
        }

        // Remove duplicates based on PID
        const uniqueRelated = allRelatedProcesses.filter((proc, index, self) =>
            index === self.findIndex(p => p.pid === proc.pid)
        );

        const relatedSection = createRelatedProcessesSection(uniqueRelated);
        if (relatedSection) {
            card.appendChild(relatedSection);
        }
    } else {
        // Create single app card
        card.className = 'app-card';

        const app = group.app;
        const port = app.listening_ports[0];
        const url = `http://localhost:${port}`;
        const projectName = getProjectName(app);
        const groupId = previewManager.getGroupId(group);
        const previewKey = `${groupId}-iframe`;

        // Set unique identifier for reconciliation
        card.setAttribute('data-group-id', groupId);

        // Header
        const header = document.createElement('div');
        header.className = 'app-card-header';

        const title = document.createElement('div');
        title.className = 'app-card-title';

        const name = document.createElement('span');
        name.className = 'app-card-name';
        name.textContent = projectName;

        const portLink = document.createElement('a');
        portLink.className = 'app-card-port';
        portLink.href = url;
        portLink.target = '_blank';
        portLink.textContent = `:${port}`;

        title.appendChild(name);
        title.appendChild(portLink);
        header.appendChild(title);

        const info = document.createElement('div');
        info.className = 'app-card-info';

        const type = document.createElement('span');
        type.className = `app-card-type type-${group.appType}`;
        type.textContent = group.appType;

        const desc = document.createElement('span');
        desc.textContent = app.description;

        info.appendChild(type);
        info.appendChild(desc);
        header.appendChild(info);

        // Preview - use zoomed-out iframe for thumbnail effect
        const preview = document.createElement('div');
        preview.className = 'app-card-preview';
        preview.setAttribute('data-preview-key', previewKey);
        preview.style.overflow = 'hidden';
        preview.style.position = 'relative';
        preview.style.height = '240px'; // 800 * 0.3
        preview.style.width = '100%';
        preview.style.backgroundColor = '#f5f5f5';

        // Create iframe with zoom effect
        const iframe = document.createElement('iframe');
        iframe.className = 'app-iframe';
        iframe.src = url;
        iframe.sandbox = 'allow-same-origin allow-scripts allow-forms';

        // Set iframe to full browser size
        iframe.style.width = '1280px';
        iframe.style.height = '800px';
        iframe.style.border = 'none';
        iframe.style.position = 'absolute';
        iframe.style.top = '0';
        iframe.style.left = '0';

        // Scale down to fit in preview (creates thumbnail effect)
        const scale = 0.3; // 30% of original size
        iframe.style.transform = `scale(${scale})`;
        iframe.style.transformOrigin = 'top left';

        // Make it clickable to open in new tab
        iframe.style.pointerEvents = 'none';
        const overlay = document.createElement('div');
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.cursor = 'pointer';
        overlay.style.zIndex = '10';
        overlay.onclick = () => window.open(url, '_blank');

        preview.appendChild(iframe);
        preview.appendChild(overlay);

        // Footer with actions
        const footer = document.createElement('div');
        footer.className = 'app-card-footer';

        const openBtn = document.createElement('a');
        openBtn.className = 'app-action primary';
        openBtn.href = url;
        openBtn.target = '_blank';
        openBtn.textContent = 'Open in Browser';

        const detailsBtn = document.createElement('button');
        detailsBtn.className = 'app-action';
        detailsBtn.textContent = 'Process Details';
        detailsBtn.onclick = () => getProcessDetails(app.pid);

        footer.appendChild(openBtn);
        footer.appendChild(detailsBtn);

        card.appendChild(header);
        card.appendChild(preview);
        card.appendChild(footer);

        // Add related processes section if available
        const relatedSection = createRelatedProcessesSection(app.related_processes);
        if (relatedSection) {
            card.appendChild(relatedSection);
        }
    }

    return card;
}

// Create single app element for grouped view
function createSingleAppElement(app, label, groupId) {
    const element = document.createElement('div');
    element.className = 'app-group-item';

    const port = app.listening_ports[0];
    const url = `http://localhost:${port}`;
    const previewKey = `${groupId}-iframe-${label.toLowerCase()}`;

    // Info
    const info = document.createElement('div');
    info.className = 'app-card-header';

    const title = document.createElement('div');
    title.className = 'app-card-title';

    const name = document.createElement('span');
    name.className = 'app-card-name';
    name.style.fontSize = '14px';
    name.textContent = `${label}: ${app.app_name}`;

    const portLink = document.createElement('a');
    portLink.className = 'app-card-port';
    portLink.href = url;
    portLink.target = '_blank';
    portLink.textContent = `:${port}`;

    title.appendChild(name);
    title.appendChild(portLink);
    info.appendChild(title);

    // Preview - use zoomed-out iframe for thumbnail effect
    const preview = document.createElement('div');
    preview.className = 'app-card-preview';
    preview.setAttribute('data-preview-key', previewKey);
    preview.style.overflow = 'hidden';
    preview.style.position = 'relative';
    preview.style.height = '240px'; // 800 * 0.3
    preview.style.width = '100%';
    preview.style.backgroundColor = '#f5f5f5';

    // Create iframe with zoom effect
    const iframe = document.createElement('iframe');
    iframe.className = 'app-iframe';
    iframe.src = url;
    iframe.sandbox = 'allow-same-origin allow-scripts allow-forms';

    // Set iframe to full browser size
    iframe.style.width = '1280px';
    iframe.style.height = '800px';
    iframe.style.border = 'none';
    iframe.style.position = 'absolute';
    iframe.style.top = '0';
    iframe.style.left = '0';

    // Scale down to fit in preview (creates thumbnail effect)
    const scale = 0.3; // 30% of original size
    iframe.style.transform = `scale(${scale})`;
    iframe.style.transformOrigin = 'top left';

    // Make it clickable to open in new tab
    iframe.style.pointerEvents = 'none';
    const overlay = document.createElement('div');
    overlay.style.position = 'absolute';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    overlay.style.cursor = 'pointer';
    overlay.style.zIndex = '10';
    overlay.onclick = () => window.open(url, '_blank');

    preview.appendChild(iframe);
    preview.appendChild(overlay);

    element.appendChild(info);
    element.appendChild(preview);

    return element;
}

// Toggle view function for frontend/backend switching
function toggleView(groupId, view) {
    const card = document.querySelector(`[data-group-id="${groupId}"]`);
    if (!card) return;

    // Update button states
    const buttons = card.querySelectorAll('.toggle-btn');
    buttons.forEach(btn => {
        if (btn.getAttribute('data-view') === view) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Show/hide appropriate views
    const views = card.querySelectorAll('.app-view');
    views.forEach(viewEl => {
        if (viewEl.getAttribute('data-view-type') === view) {
            viewEl.style.display = 'block';
            viewEl.classList.add('active');
        } else {
            viewEl.style.display = 'none';
            viewEl.classList.remove('active');
        }
    });
}

// Create related processes section
function createRelatedProcessesSection(relatedProcesses) {
    if (!relatedProcesses || relatedProcesses.length === 0) {
        return null;
    }

    const section = document.createElement('div');
    section.className = 'related-processes';

    const header = document.createElement('div');
    header.className = 'related-processes-header';
    header.textContent = `Bundled Processes (${relatedProcesses.length})`;

    const list = document.createElement('div');
    list.className = 'related-process-list';

    relatedProcesses.forEach(proc => {
        const item = document.createElement('div');
        item.className = 'related-process-item';

        const info = document.createElement('div');
        info.className = 'related-process-info';

        const type = document.createElement('span');
        type.className = 'related-process-type';
        type.textContent = proc.type;

        const name = document.createElement('span');
        name.className = 'related-process-name';
        name.textContent = proc.name;

        info.appendChild(type);
        info.appendChild(name);

        // Add port badge if this is a backend server
        if (proc.type === 'Backend Server' && proc.ports && proc.ports.length > 0) {
            const portBadge = document.createElement('a');
            portBadge.className = 'related-process-port';
            portBadge.href = `http://localhost:${proc.ports[0]}`;
            portBadge.target = '_blank';
            portBadge.textContent = `:${proc.ports[0]}`;
            portBadge.onclick = (e) => e.stopPropagation();
            info.appendChild(portBadge);
        }

        const stats = document.createElement('div');
        stats.className = 'related-process-stats';

        const cpuStat = document.createElement('span');
        cpuStat.className = 'related-process-stat';
        cpuStat.innerHTML = `<strong>CPU:</strong> ${proc.cpu_percent.toFixed(1)}%`;

        const memStat = document.createElement('span');
        memStat.className = 'related-process-stat';
        memStat.innerHTML = `<strong>MEM:</strong> ${proc.memory_mb.toFixed(1)} MB`;

        stats.appendChild(cpuStat);
        stats.appendChild(memStat);

        item.appendChild(info);
        item.appendChild(stats);

        list.appendChild(item);
    });

    section.appendChild(header);
    section.appendChild(list);

    return section;
}

function updateSystemInfo(systemInfo) {
    const cpuValue = systemInfo.cpu_percent.toFixed(1);
    const memValue = systemInfo.memory_percent.toFixed(1);

    // Update with terminal-style formatting
    document.getElementById('cpu-usage').innerHTML = `CPU: <span class="metric">${cpuValue}</span>%`;
    document.getElementById('memory-usage').innerHTML = `MEM: <span class="metric">${memValue}</span>%`;

    // Add warning color if CPU/MEM is high
    const cpuElement = document.getElementById('cpu-usage');
    const memElement = document.getElementById('memory-usage');

    if (parseFloat(cpuValue) > 80) {
        cpuElement.style.color = 'var(--terminal-red)';
    } else if (parseFloat(cpuValue) > 50) {
        cpuElement.style.color = 'var(--terminal-yellow)';
    } else {
        cpuElement.style.color = 'var(--terminal-text-dim)';
    }

    if (parseFloat(memValue) > 80) {
        memElement.style.color = 'var(--terminal-red)';
    } else if (parseFloat(memValue) > 50) {
        memElement.style.color = 'var(--terminal-yellow)';
    } else {
        memElement.style.color = 'var(--terminal-text-dim)';
    }
}

// Table rendering functions removed - preview-only view

// Kill functionality removed for safety
// function killProcess(pid) {
//     if (confirm(`Are you sure you want to kill process ${pid}?`)) {
//         socket.emit('kill_process', { pid: pid });
//     }
// }

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Auto-refresh every 2 seconds
setInterval(() => {
    if (autoRefresh) {
        requestProcesses();
    }
}, 2000);

// Terminal boot sequence
function bootSequence() {
    terminalLog('PROCESS_VIEWER.EXE v2.1.0 - INITIALIZING...', 'info');
    terminalLog('LOADING SYSTEM MODULES...', 'info');

    setTimeout(() => {
        terminalLog('ESTABLISHING WEBSOCKET CONNECTION...', 'info');
    }, 300);

    setTimeout(() => {
        terminalLog('SYSTEM READY - MONITORING ACTIVE', 'info');
    }, 600);
}

// Run boot sequence on page load
document.addEventListener('DOMContentLoaded', () => {
    bootSequence();
});

// Initial load
requestProcesses();