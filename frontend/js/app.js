/**
 * QADIR — Frontend Application
 * Clean. Fast. No frameworks. Vanilla JS.
 */

const API = '';  // Same origin
let currentSoul = 'qadir';
let isTyping = false;

// ─── Init ───────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initChat();
    initSoulSelector();
    loadStatus();
    loadProviders();
    loadAgents();
});

// ─── Navigation ─────────────────────────────────────────

function initNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            switchView(view);
        });
    });
}

function switchView(viewName) {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');
    document.getElementById(`view-${viewName}`).classList.add('active');

    if (viewName === 'settings') loadSettings();
    if (viewName === 'memory') loadMemory();
    if (viewName === 'agents') loadAgents();
}

// ─── Chat ───────────────────────────────────────────────

function initChat() {
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    sendBtn.addEventListener('click', sendMessage);
}

function initSoulSelector() {
    document.querySelectorAll('.soul-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.soul-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            currentSoul = chip.dataset.soul;

            // Update welcome message
            const welcomeIcon = document.querySelector('.welcome-icon');
            const welcomeTitle = document.querySelector('.welcome-message h2');
            if (currentSoul === 'zait') {
                welcomeIcon.textContent = '🛡️';
                welcomeTitle.textContent = 'As-salamu alaykum. I\'m Zait.';
            } else {
                welcomeIcon.textContent = '🧠';
                welcomeTitle.textContent = '. I\'m Qadir.';
            }
        });
    });
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const content = input.value.trim();
    if (!content || isTyping) return;

    // Clear input
    input.value = '';
    input.style.height = 'auto';

    // Remove welcome message
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    // Add user message
    addMessage('user', content);

    // Show typing indicator
    showTyping();
    isTyping = true;

    try {
        const response = await fetch(`${API}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: content,
                soul: currentSoul,
                task_type: 'general'
            })
        });

        const data = await response.json();
        hideTyping();

        if (data.success) {
            addMessage('assistant', data.content, {
                brain: `${data.provider}/${data.model}`,
                latency: data.latency_ms
            });
            document.getElementById('currentBrain').textContent = `${data.provider}/${data.model}`;
        } else {
            addMessage('assistant', `Error: ${data.content}`, { brain: 'error' });
        }
    } catch (err) {
        hideTyping();
        addMessage('assistant', `Connection error: ${err.message}. Is the backend running?`, { brain: 'error' });
    }

    isTyping = false;
}

function addMessage(role, content, meta = {}) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : (currentSoul === 'zait' ? '🛡️' : '🧠');

    let metaHtml = '';
    if (meta.brain) {
        metaHtml = `<div class="message-meta">
            <span>${meta.brain}</span>
            ${meta.latency ? `<span>${meta.latency}ms</span>` : ''}
        </div>`;
    }

    div.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div>
            <div class="message-content">${escapeHtml(content)}</div>
            ${metaHtml}
        </div>
    `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function showTyping() {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'message assistant';
    div.id = 'typingIndicator';
    div.innerHTML = `
        <div class="message-avatar">${currentSoul === 'zait' ? '🛡️' : '🧠'}</div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function hideTyping() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

// ─── Status ─────────────────────────────────────────────

async function loadStatus() {
    try {
        const res = await fetch(`${API}/api/status`);
        const data = await res.json();

        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');

        if (data.providers_connected && data.providers_connected.length > 0) {
            dot.classList.add('online');
            text.textContent = `${data.providers_connected.length} brains connected`;
        } else {
            text.textContent = 'No API keys configured';
        }
    } catch (err) {
        document.getElementById('statusText').textContent = 'Offline';
    }
}

async function loadProviders() {
    try {
        const res = await fetch(`${API}/api/providers`);
        const data = await res.json();

        const grid = document.getElementById('apiKeysGrid');
        if (!grid) return;

        grid.innerHTML = '';
        for (const [key, provider] of Object.entries(data)) {
            const row = document.createElement('div');
            row.className = 'api-key-row';
            row.innerHTML = `
                <span class="api-key-provider">${provider.name}</span>
                <span class="api-key-status ${provider.connected ? 'connected' : 'disconnected'}">
                    ${provider.connected ? '● Connected' : '○ Disconnected'}
                </span>
                <input type="password" class="api-key-input" placeholder="API Key"
                       data-provider="${key}" value="${provider.has_key ? '••••••••' : ''}">
                <button class="btn-primary btn-small" onclick="saveKey('${key}', this)">Save</button>
            `;
            grid.appendChild(row);
        }
    } catch (err) {
        console.error('Failed to load providers:', err);
    }
}

async function saveKey(provider, btn) {
    const input = btn.parentElement.querySelector('.api-key-input');
    const key = input.value.trim();
    if (!key || key === '••••••••') return;

    btn.textContent = '...';
    try {
        await fetch(`${API}/api/keys`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, api_key: key })
        });
        btn.textContent = '✓';
        input.value = '••••••••';
        loadStatus();
        setTimeout(() => btn.textContent = 'Save', 2000);
    } catch (err) {
        btn.textContent = '✗';
        setTimeout(() => btn.textContent = 'Save', 2000);
    }
}

// ─── Agents View ────────────────────────────────────────

async function loadAgents() {
    try {
        const res = await fetch(`${API}/api/souls`);
        const data = await res.json();

        const grid = document.getElementById('agentsGrid');
        grid.innerHTML = '';

        for (const [key, soul] of Object.entries(data)) {
            const card = document.createElement('div');
            card.className = 'agent-card';
            card.innerHTML = `
                <div class="agent-card-header">
                    <span class="agent-emoji">${soul.emoji}</span>
                    <div>
                        <div class="agent-name">${soul.name}</div>
                        <div class="agent-role">${soul.role}</div>
                    </div>
                </div>
                <div class="agent-stats">
                    <span>NZT Active</span>
                    <span>24/7</span>
                </div>
            `;
            card.addEventListener('click', () => {
                switchView('chat');
                document.querySelectorAll('.soul-chip').forEach(c => c.classList.remove('active'));
                document.querySelector(`[data-soul="${key}"]`)?.classList.add('active');
                currentSoul = key;
            });
            grid.appendChild(card);
        }
    } catch (err) {
        console.error('Failed to load agents:', err);
    }
}

// ─── Memory View ────────────────────────────────────────

async function loadMemory() {
    const list = document.getElementById('memoryList');
    list.innerHTML = '<p style="color: var(--text-dim);">Search memory to view entries.</p>';

    const searchInput = document.getElementById('memorySearch');
    searchInput.oninput = async () => {
        const q = searchInput.value.trim();
        if (q.length < 2) return;

        try {
            const res = await fetch(`${API}/api/memory/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();

            list.innerHTML = '';
            if (data.length === 0) {
                list.innerHTML = '<p style="color: var(--text-dim);">No results found.</p>';
                return;
            }

            data.forEach(item => {
                const div = document.createElement('div');
                div.className = 'memory-item';
                div.innerHTML = `
                    <div class="memory-key">${escapeHtml(item.key)}</div>
                    <div class="memory-value">${escapeHtml(item.value.substring(0, 200))}</div>
                `;
                list.appendChild(div);
            });
        } catch (err) {
            list.innerHTML = '<p style="color: var(--error);">Search failed.</p>';
        }
    };
}

// ─── Settings View ──────────────────────────────────────

async function loadSettings() {
    loadProviders();

    try {
        const res = await fetch(`${API}/api/status`);
        const data = await res.json();

        const statusDiv = document.getElementById('brainStatus');
        statusDiv.innerHTML = '';

        data.providers_connected.forEach(provider => {
            const row = document.createElement('div');
            row.className = 'info-row';
            row.innerHTML = `<span>${provider}</span><span style="color: var(--success);">● Online</span>`;
            statusDiv.appendChild(row);
        });

        if (data.providers_connected.length === 0) {
            statusDiv.innerHTML = '<p style="color: var(--text-dim);">No providers connected. Add API keys above.</p>';
        }
    } catch (err) {
        console.error('Failed to load brain status:', err);
    }
}

// ─── Utilities ──────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
