/* ═══════════════════════════════════════════════════════════════════════
   Penless — Frontend Application Logic
   ═══════════════════════════════════════════════════════════════════════ */

// ─── State ──────────────────────────────────────────────────────────────
let currentPath = '';
let pin = '';
let pinRequired = false;
let serverStatus = null;

// ─── Initialization ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    init();
});

async function init() {
    // Set up click handler for drop zone
    document.getElementById('drop-zone').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });

    // Enter key on PIN input
    document.getElementById('pin-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitPin();
    });

    // Enter key on new folder input
    document.getElementById('new-folder-name').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') createFolder();
        if (e.key === 'Escape') hideNewFolderDialog();
    });

    await checkStatus();
}

// ─── Status & Auth ──────────────────────────────────────────────────────
async function checkStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) throw new Error('Server unreachable');

        serverStatus = await res.json();

        // Update connection status
        setConnectionStatus('connected', 'Connected');

        // Update server info
        document.getElementById('server-ip').textContent = serverStatus.url;
        document.getElementById('max-upload').textContent = serverStatus.maxUploadSizeFormatted;

        // Check if PIN is required
        if (serverStatus.pinRequired) {
            pinRequired = true;
            showPinModal();
        } else {
            pinRequired = false;
            refreshFiles();
        }
    } catch (err) {
        setConnectionStatus('error', 'Disconnected');
        showToast('Cannot connect to server. Make sure you are on the same network.', 'error');
    }
}

function setConnectionStatus(status, text) {
    const badge = document.getElementById('connection-status');
    const statusText = document.getElementById('status-text');
    badge.className = `status-badge status-${status}`;
    statusText.textContent = text;
}

// ─── PIN Authentication ─────────────────────────────────────────────────
function showPinModal() {
    document.getElementById('pin-modal').style.display = 'flex';
    setTimeout(() => document.getElementById('pin-input').focus(), 100);
}

function hidePinModal() {
    document.getElementById('pin-modal').style.display = 'none';
}

async function submitPin() {
    const input = document.getElementById('pin-input');
    const errorEl = document.getElementById('pin-error');
    const enteredPin = input.value.trim();

    if (!enteredPin) {
        errorEl.textContent = 'Please enter a PIN.';
        errorEl.style.display = 'block';
        return;
    }

    try {
        const res = await fetch('/api/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: enteredPin })
        });

        const data = await res.json();

        if (data.authenticated) {
            pin = enteredPin;
            hidePinModal();
            showToast('Access granted!', 'success');
            refreshFiles();
        } else {
            errorEl.textContent = data.error || 'Incorrect PIN.';
            errorEl.style.display = 'block';
            input.value = '';
            input.focus();
        }
    } catch (err) {
        errorEl.textContent = 'Connection error. Please try again.';
        errorEl.style.display = 'block';
    }
}

function getHeaders() {
    const headers = {};
    if (pin) headers['X-Pin'] = pin;
    return headers;
}

function getPinQuery() {
    return pin ? `pin=${encodeURIComponent(pin)}` : '';
}

// ─── File Browsing ──────────────────────────────────────────────────────
async function refreshFiles() {
    const fileList = document.getElementById('file-list');
    const emptyState = document.getElementById('empty-state');

    fileList.innerHTML = `
        <div class="file-list-loading">
            <div class="spinner"></div>
            <p>Loading files...</p>
        </div>`;
    emptyState.style.display = 'none';

    try {
        const url = `/api/files?path=${encodeURIComponent(currentPath)}&${getPinQuery()}`;
        const res = await fetch(url, { headers: getHeaders() });

        if (res.status === 401) {
            showPinModal();
            return;
        }

        if (!res.ok) throw new Error('Failed to load files');

        const data = await res.json();
        renderBreadcrumb(data.currentPath);
        renderFiles(data);
        updateUploadFolderLabel(data.currentPath);
    } catch (err) {
        fileList.innerHTML = `
            <div class="file-list-loading">
                <p style="color: var(--danger);">Failed to load files. <a href="#" onclick="refreshFiles(); return false;" style="color: var(--primary);">Retry</a></p>
            </div>`;
    }
}

function renderBreadcrumb(path) {
    const breadcrumb = document.getElementById('breadcrumb');
    let html = `<span class="breadcrumb-item ${!path ? 'active' : ''}" onclick="navigateTo('')">🏠 Home</span>`;

    if (path) {
        const parts = path.split('/');
        let accumulated = '';
        parts.forEach((part, i) => {
            accumulated += (i === 0 ? '' : '/') + part;
            const isLast = i === parts.length - 1;
            html += `<span class="breadcrumb-separator">›</span>`;
            html += `<span class="breadcrumb-item ${isLast ? 'active' : ''}" onclick="navigateTo('${escapeAttr(accumulated)}')">${escapeHtml(part)}</span>`;
        });
    }

    breadcrumb.innerHTML = html;
}

function renderFiles(data) {
    const fileList = document.getElementById('file-list');
    const emptyState = document.getElementById('empty-state');

    if (data.folders.length === 0 && data.files.length === 0) {
        fileList.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';
    let html = '';

    // Folders first
    data.folders.forEach(folder => {
        const safePath = escapeAttr(folder.path);
        const safeName = escapeAttr(folder.name);
        html += `
            <div class="file-item">
                <div class="file-item-icon">📁</div>
                <div class="file-item-info">
                    <div class="file-item-name folder-name" onclick="navigateTo('${safePath}')">${escapeHtml(folder.name)}</div>
                    <div class="file-item-meta">
                        <span>${folder.itemCount} items</span>
                        <span>${formatDate(folder.modified)}</span>
                    </div>
                </div>
                <div class="file-item-actions">
                    <button class="btn btn-ghost btn-sm" onclick="startRename('${safePath}', '${safeName}', this)" title="Rename">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="deleteFolder('${safePath}', '${safeName}')" title="Delete Folder">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>`;
    });

    // Files
    data.files.forEach(file => {
        const icon = getFileIcon(file.extension);
        const pinParam = getPinQuery();
        const downloadUrl = `/api/files/download?path=${encodeURIComponent(file.path)}${pinParam ? '&' + pinParam : ''}`;
        const safePath = escapeAttr(file.path);
        const safeName = escapeAttr(file.name);

        html += `
            <div class="file-item">
                <div class="file-item-icon">${icon}</div>
                <div class="file-item-info">
                    <div class="file-item-name">${escapeHtml(file.name)}</div>
                    <div class="file-item-meta">
                        <span>${formatSize(file.size)}</span>
                        <span>${formatDate(file.modified)}</span>
                    </div>
                </div>
                <div class="file-item-actions">
                    <a href="${downloadUrl}" class="btn btn-download btn-sm" download>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        Download
                    </a>
                    <button class="btn btn-ghost btn-sm" onclick="startRename('${safePath}', '${safeName}', this)" title="Rename">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="deleteFile('${safePath}', '${safeName}')" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>`;
    });

    fileList.innerHTML = html;
}

function navigateTo(path) {
    currentPath = path;
    refreshFiles();
}

function updateUploadFolderLabel(path) {
    document.getElementById('upload-folder-label').textContent = path || 'root';
}

// ─── File Upload ────────────────────────────────────────────────────────
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFiles(files);
    }
}

function handleFileSelect(files) {
    if (files.length > 0) {
        uploadFiles(files);
    }
}

async function uploadFiles(files) {
    const progressArea = document.getElementById('upload-progress');
    const uploadBar = document.getElementById('upload-bar');
    const uploadStatus = document.getElementById('upload-status');
    const uploadCount = document.getElementById('upload-count');
    const uploadResults = document.getElementById('upload-results');

    progressArea.style.display = 'block';
    uploadResults.innerHTML = '';
    uploadBar.style.width = '0%';
    uploadStatus.textContent = 'Uploading...';
    uploadCount.textContent = `0/${files.length}`;

    const formData = new FormData();
    for (const file of files) {
        formData.append('files', file);
    }

    try {
        const pinParam = getPinQuery();
        const folderParam = `folder=${encodeURIComponent(currentPath)}`;
        const query = [folderParam, pinParam].filter(Boolean).join('&');

        const xhr = new XMLHttpRequest();
        xhr.open('POST', `/api/upload?${query}`);

        if (pin) {
            xhr.setRequestHeader('X-Pin', pin);
        }

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                uploadBar.style.width = pct + '%';
                uploadStatus.textContent = `Uploading... ${pct}%`;
            }
        };

        xhr.onload = () => {
            if (xhr.status === 200) {
                const result = JSON.parse(xhr.responseText);
                uploadBar.style.width = '100%';
                uploadStatus.textContent = 'Upload complete!';
                uploadCount.textContent = `${result.uploaded}/${files.length}`;

                let resultsHtml = '';
                result.files.forEach(f => {
                    if (f.error) {
                        resultsHtml += `<div class="upload-result-item"><span class="error">✕</span> ${escapeHtml(f.name)}: ${escapeHtml(f.error)}</div>`;
                    } else {
                        resultsHtml += `<div class="upload-result-item"><span class="success">✓</span> ${escapeHtml(f.name)} (${f.sizeFormatted})</div>`;
                    }
                });
                uploadResults.innerHTML = resultsHtml;

                showToast(`${result.uploaded} file(s) uploaded successfully!`, 'success');
                refreshFiles();

                // Hide progress after 5s
                setTimeout(() => {
                    progressArea.style.display = 'none';
                }, 5000);
            } else if (xhr.status === 401) {
                showPinModal();
                uploadStatus.textContent = 'Authentication required';
            } else {
                uploadStatus.textContent = 'Upload failed';
                showToast('Upload failed. Please try again.', 'error');
            }
        };

        xhr.onerror = () => {
            uploadStatus.textContent = 'Upload failed — network error';
            showToast('Network error during upload.', 'error');
        };

        xhr.send(formData);
    } catch (err) {
        uploadStatus.textContent = 'Upload failed';
        showToast('Upload error: ' + err.message, 'error');
    }

    // Reset file input
    document.getElementById('file-input').value = '';
}

// ─── File Actions ────────────────────────────────────────────────────────
async function deleteFile(path, name) {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;

    try {
        const pinParam = getPinQuery();
        const res = await fetch(`/api/files?path=${encodeURIComponent(path)}${pinParam ? '&' + pinParam : ''}`, {
            method: 'DELETE',
            headers: getHeaders()
        });

        if (res.status === 401) { showPinModal(); return; }

        if (res.ok) {
            showToast(`"${name}" deleted.`, 'success');
            refreshFiles();
        } else {
            const data = await res.json();
            showToast(data.error || 'Delete failed.', 'error');
        }
    } catch (err) {
        showToast('Error deleting file.', 'error');
    }
}

async function deleteFolder(path, name) {
    if (!confirm(`Delete folder "${name}" and ALL its contents? This cannot be undone.`)) return;

    try {
        const pinParam = getPinQuery();
        const res = await fetch(`/api/folders?path=${encodeURIComponent(path)}${pinParam ? '&' + pinParam : ''}`, {
            method: 'DELETE',
            headers: getHeaders()
        });

        if (res.status === 401) { showPinModal(); return; }

        if (res.ok) {
            showToast(`Folder "${name}" deleted.`, 'success');
            refreshFiles();
        } else {
            const data = await res.json();
            showToast(data.error || 'Delete failed.', 'error');
        }
    } catch (err) {
        showToast('Error deleting folder.', 'error');
    }
}

// ─── Rename ──────────────────────────────────────────────────────────────
function startRename(path, currentName, triggerBtn) {
    const fileItem = triggerBtn.closest('.file-item');
    if (!fileItem) return;

    const nameEl = fileItem.querySelector('.file-item-name');
    if (!nameEl) return;

    const ext = currentName.includes('.') ? currentName.slice(currentName.lastIndexOf('.')) : '';

    nameEl.innerHTML = `
        <div class="rename-row">
            <input id="rename-input-field" class="input rename-input"
                   value="${escapeHtml(currentName)}" maxlength="255"
                   onclick="event.stopPropagation()">
            <button class="btn btn-primary btn-sm" style="margin-left:6px;"
                    onclick="commitRename('${escapeAttr(path)}')">Save</button>
            <button class="btn btn-ghost btn-sm" onclick="refreshFiles()">✕</button>
        </div>`;

    const input = document.getElementById('rename-input-field');
    input.focus();
    // Select only the base name (not extension) for convenience
    const selEnd = ext ? currentName.length - ext.length : currentName.length;
    input.setSelectionRange(0, selEnd);

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commitRename(path); }
        if (e.key === 'Escape') { refreshFiles(); }
    });
}

async function commitRename(path) {
    const input = document.getElementById('rename-input-field');
    if (!input) return;
    const newName = input.value.trim();
    if (!newName) { showToast('Name cannot be empty.', 'error'); return; }

    try {
        const pinParam = getPinQuery();
        const query = `path=${encodeURIComponent(path)}&newName=${encodeURIComponent(newName)}${pinParam ? '&' + pinParam : ''}`;
        const res = await fetch(`/api/files?${query}`, {
            method: 'PATCH',
            headers: getHeaders()
        });

        if (res.status === 401) { showPinModal(); return; }

        if (res.ok) {
            showToast(`Renamed to "${newName}".`, 'success');
            refreshFiles();
        } else {
            const data = await res.json();
            showToast(data.error || 'Rename failed.', 'error');
        }
    } catch (err) {
        showToast('Error renaming item.', 'error');
    }
}

// ─── Folder Creation ────────────────────────────────────────────────────
function showNewFolderDialog() {
    const dialog = document.getElementById('new-folder-dialog');
    dialog.style.display = 'flex';
    const input = document.getElementById('new-folder-name');
    input.value = '';
    input.focus();
}

function hideNewFolderDialog() {
    document.getElementById('new-folder-dialog').style.display = 'none';
}

async function createFolder() {
    const name = document.getElementById('new-folder-name').value.trim();
    if (!name) {
        showToast('Please enter a folder name.', 'error');
        return;
    }

    try {
        const pinParam = getPinQuery();
        const pathParam = `path=${encodeURIComponent(currentPath)}`;
        const nameParam = `name=${encodeURIComponent(name)}`;
        const query = [pathParam, nameParam, pinParam].filter(Boolean).join('&');

        const res = await fetch(`/api/folders?${query}`, {
            method: 'POST',
            headers: getHeaders()
        });

        if (res.status === 401) {
            showPinModal();
            return;
        }

        if (res.ok) {
            hideNewFolderDialog();
            showToast(`Folder "${name}" created.`, 'success');
            refreshFiles();
        } else {
            const data = await res.json();
            showToast(data.error || 'Failed to create folder.', 'error');
        }
    } catch (err) {
        showToast('Error creating folder.', 'error');
    }
}

// ─── Toast Notifications ────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${escapeHtml(message)}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ─── Utility Functions ──────────────────────────────────────────────────
function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
    if (diff < 604800000) return Math.floor(diff / 86400000) + 'd ago';

    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
}

function getFileIcon(ext) {
    const icons = {
        // Images
        jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', svg: '🖼️', webp: '🖼️', bmp: '🖼️', ico: '🖼️',
        // Videos
        mp4: '🎬', avi: '🎬', mkv: '🎬', mov: '🎬', wmv: '🎬', flv: '🎬', webm: '🎬',
        // Audio
        mp3: '🎵', wav: '🎵', flac: '🎵', aac: '🎵', ogg: '🎵', wma: '🎵',
        // Documents
        pdf: '📕', doc: '📝', docx: '📝', txt: '📄', rtf: '📝',
        // Spreadsheets
        xls: '📊', xlsx: '📊', csv: '📊',
        // Presentations
        ppt: '📈', pptx: '📈',
        // Archives
        zip: '📦', rar: '📦', '7z': '📦', tar: '📦', gz: '📦',
        // Code
        js: '💻', ts: '💻', py: '💻', java: '💻', cs: '💻', cpp: '💻', c: '💻', html: '💻', css: '💻', json: '💻', xml: '💻',
        // Executables
        exe: '⚙️', msi: '⚙️', bat: '⚙️', cmd: '⚙️', ps1: '⚙️',
        // Disk images
        iso: '💿', img: '💿',
    };
    return icons[ext] || '📄';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/** Escape a value for safe use inside an HTML attribute (e.g. onclick='...') */
function escapeAttr(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/'/g, '&#39;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
