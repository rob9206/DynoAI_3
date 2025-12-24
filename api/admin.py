"""
DynoAI Backend Admin UI
A simple, self-contained admin dashboard for the API.
"""

from flask import Blueprint, render_template_string
from datetime import datetime
import os
import sys

admin_bp = Blueprint('admin', __name__)

ADMIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DynoAI Admin</title>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-tertiary: #1a1a24;
            --accent: #f97316;
            --accent-glow: rgba(249, 115, 22, 0.3);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --success: #22c55e;
            --warning: #eab308;
            --danger: #ef4444;
            --border: #2d2d3a;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at top, rgba(249, 115, 22, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at bottom right, rgba(59, 130, 246, 0.05) 0%, transparent 50%);
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .logo-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--accent), #fb923c);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            box-shadow: 0 0 30px var(--accent-glow);
        }
        
        .logo h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .logo span {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: var(--bg-tertiary);
            border-radius: 999px;
            font-size: 0.875rem;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }
        
        .card:hover {
            border-color: var(--accent);
            box-shadow: 0 0 40px rgba(249, 115, 22, 0.1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .card-title {
            font-size: 0.875rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .card-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent);
        }
        
        .endpoints-card {
            grid-column: 1 / -1;
        }
        
        .endpoint-list {
            display: grid;
            gap: 0.5rem;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .endpoint {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 0.75rem 1rem;
            background: var(--bg-tertiary);
            border-radius: 8px;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        
        .endpoint:hover {
            background: var(--bg-primary);
            transform: translateX(4px);
        }
        
        .method {
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            min-width: 60px;
            text-align: center;
        }
        
        .method-get { background: #22c55e33; color: #22c55e; }
        .method-post { background: #3b82f633; color: #3b82f6; }
        .method-put { background: #eab30833; color: #eab308; }
        .method-delete { background: #ef444433; color: #ef4444; }
        
        .endpoint-path {
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
            flex: 1;
        }
        
        .endpoint-desc {
            color: var(--text-secondary);
            font-size: 0.75rem;
        }
        
        .test-panel {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        
        .test-header {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        
        .test-input {
            flex: 1;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .test-input:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        .test-btn {
            background: linear-gradient(135deg, var(--accent), #fb923c);
            border: none;
            border-radius: 8px;
            padding: 0.75rem 1.5rem;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .test-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px var(--accent-glow);
        }
        
        .test-output {
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 300px;
            overflow-y: auto;
            color: var(--success);
        }
        
        .test-output.error { color: var(--danger); }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
            font-size: 0.875rem;
        }
        
        .info-label { color: var(--text-secondary); }
        .info-value { color: var(--text-primary); text-align: right; }
        
        select.test-input {
            min-width: 100px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                <div class="logo-icon">🔧</div>
                <div>
                    <h1>DynoAI Admin</h1>
                    <span>Backend Control Panel</span>
                </div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>API Online</span>
            </div>
        </header>
        
        <div class="grid">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Version</span>
                </div>
                <div class="card-value">{{ version }}</div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Uptime</span>
                </div>
                <div class="card-value" id="uptime">--</div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Total Endpoints</span>
                </div>
                <div class="card-value">{{ endpoints|length }}</div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Python</span>
                </div>
                <div class="card-value" style="font-size: 1rem;">{{ python_version }}</div>
            </div>
        </div>
        
        <div class="card endpoints-card">
            <div class="card-header">
                <span class="card-title">API Endpoints</span>
            </div>
            <div class="endpoint-list">
                {% for endpoint in endpoints %}
                <div class="endpoint" onclick="setEndpoint('{{ endpoint.path }}', '{{ endpoint.methods[0] }}')">
                    {% for method in endpoint.methods %}
                    <span class="method method-{{ method|lower }}">{{ method }}</span>
                    {% endfor %}
                    <span class="endpoint-path">{{ endpoint.path }}</span>
                    <span class="endpoint-desc">{{ endpoint.desc }}</span>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="test-panel">
            <h3 style="margin-bottom: 1rem; color: var(--text-secondary);">🧪 Test Endpoint</h3>
            <div class="test-header">
                <select class="test-input" id="testMethod">
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                </select>
                <input type="text" class="test-input" id="testUrl" placeholder="/api/health" value="/api/health">
                <button class="test-btn" onclick="testEndpoint()">Execute</button>
            </div>
            <div class="test-output" id="testOutput">Click an endpoint above or enter a URL to test...</div>
        </div>
        
        <div class="card" style="margin-top: 2rem;">
            <div class="card-header">
                <span class="card-title">System Info</span>
            </div>
            <div class="info-grid">
                <span class="info-label">Host</span>
                <span class="info-value">{{ host }}</span>
                <span class="info-label">Port</span>
                <span class="info-value">{{ port }}</span>
                <span class="info-label">Upload Folder</span>
                <span class="info-value">{{ upload_folder }}</span>
                <span class="info-label">Output Folder</span>
                <span class="info-value">{{ output_folder }}</span>
                <span class="info-label">Rate Limiting</span>
                <span class="info-value">{{ rate_limit }}</span>
            </div>
        </div>
    </div>
    
    <script>
        const startTime = Date.now();
        
        function updateUptime() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const hours = Math.floor(elapsed / 3600);
            const minutes = Math.floor((elapsed % 3600) / 60);
            const seconds = elapsed % 60;
            document.getElementById('uptime').textContent = 
                `${hours}h ${minutes}m ${seconds}s`;
        }
        
        setInterval(updateUptime, 1000);
        updateUptime();
        
        function setEndpoint(path, method) {
            document.getElementById('testUrl').value = path;
            document.getElementById('testMethod').value = method;
        }
        
        async function testEndpoint() {
            const method = document.getElementById('testMethod').value;
            const url = document.getElementById('testUrl').value;
            const output = document.getElementById('testOutput');
            
            output.textContent = 'Loading...';
            output.className = 'test-output';
            
            try {
                const response = await fetch(url, { method });
                const data = await response.text();
                
                try {
                    const json = JSON.parse(data);
                    output.textContent = JSON.stringify(json, null, 2);
                } catch {
                    output.textContent = data;
                }
                
                output.className = response.ok ? 'test-output' : 'test-output error';
            } catch (err) {
                output.textContent = 'Error: ' + err.message;
                output.className = 'test-output error';
            }
        }
        
        // Auto-test health on load
        setTimeout(testEndpoint, 500);
    </script>
</body>
</html>
'''

@admin_bp.route('/admin')
def admin_dashboard():
    """Render the admin dashboard."""
    from flask import current_app, request
    
    # Get version
    try:
        from dynoai.version import __version__
        version = __version__
    except:
        version = "1.2.1"
    
    # Collect endpoints
    endpoints = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint != 'static' and not rule.rule.startswith('/flasgger'):
            methods = [m for m in rule.methods if m not in ('HEAD', 'OPTIONS')]
            if methods:
                # Generate description from endpoint name
                desc = rule.endpoint.replace('_', ' ').replace('.', ' - ').title()
                endpoints.append({
                    'path': rule.rule,
                    'methods': sorted(methods),
                    'desc': desc
                })
    
    # Sort by path
    endpoints.sort(key=lambda x: x['path'])
    
    # Get config values
    upload_folder = str(current_app.config.get('UPLOAD_FOLDER', 'uploads'))
    output_folder = str(current_app.config.get('OUTPUT_FOLDER', 'outputs'))
    
    return render_template_string(ADMIN_HTML,
        version=version,
        endpoints=endpoints,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        host=request.host.split(':')[0],
        port=request.host.split(':')[1] if ':' in request.host else '5001',
        upload_folder=upload_folder,
        output_folder=output_folder,
        rate_limit='Enabled'
    )

