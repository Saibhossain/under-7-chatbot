import os
from flask import Flask, render_template_string, abort

app = Flask(__name__)

# Base directory for the protopype
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pages_meta = {
    "app": {
        "title": "Barnaby's Magic English Adventure (Main Hub)",
        "emoji": "🧸",
        "file_path": "full_protopype/app.py",
        "description": "The integrated hub combining the Kids Playroom and the Parental Control Panel into a single cohesive interface.",
        "streamlit_url": "https://share.streamlit.io/saibhossain/under-7-chatbot/main/full_protopype/app.py"
    },
    "kids": {
        "title": "Kids Playroom",
        "emoji": "🎒",
        "file_path": "full_protopype/app_kids.py",
        "description": "A simplified, gamified child-facing interface focusing entirely on the chat companion, voice feedback, and visual encouragement.",
        "streamlit_url": "https://share.streamlit.io/saibhossain/under-7-chatbot/main/full_protopype/app_kids.py"
    },
    "parent": {
        "title": "Parental Control Panel",
        "emoji": "🔐",
        "file_path": "full_protopype/app_parent.py",
        "description": "The analytics dashboard for parents to audit chat history transcripts, review psychologist evaluations, and override level/mode settings.",
        "streamlit_url": "https://share.streamlit.io/saibhossain/under-7-chatbot/main/full_protopype/app_parent.py"
    },
    "db_explorer": {
        "title": "Database Explorer",
        "emoji": "🔍",
        "file_path": "full_protopype/app_db_explorer.py",
        "description": "An administrative utility to inspect the SQLite schemas, run custom SQL queries, and view logs directly from the companion database.",
        "streamlit_url": "https://share.streamlit.io/saibhossain/under-7-chatbot/main/full_protopype/app_db_explorer.py"
    }
}

def render_page(page_key):
    meta = pages_meta.get(page_key)
    if not meta:
        abort(404)
        
    # Read the file content
    file_abs_path = os.path.join(BASE_DIR, meta["file_path"])
    code_content = ""
    if os.path.exists(file_abs_path):
        with open(file_abs_path, "r", encoding="utf-8") as f:
            code_content = f.read()
    else:
        code_content = f"# File {meta['file_path']} not found on server."
        
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ meta['title'] }} - Vercel Cloud Portal</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #4A90E2;
                --primary-bg: rgba(74, 144, 226, 0.1);
                --dark: #1E293B;
                --gray: #64748B;
                --light-gray: #F1F5F9;
                --bg: #F8FAFC;
                --card-bg: #FFFFFF;
                --border: #E2E8F0;
            }
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }
            body {
                font-family: 'Outfit', sans-serif;
                background-color: var(--bg);
                color: var(--dark);
                line-height: 1.5;
                padding-bottom: 60px;
            }
            header {
                background: linear-gradient(135deg, #4A90E2, #357ABD);
                color: white;
                padding: 40px 20px;
                text-align: center;
                border-bottom-left-radius: 30px;
                border-bottom-right-radius: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            }
            .header-content {
                max-width: 1000px;
                margin: 0 auto;
            }
            .emoji {
                font-size: 70px;
                margin-bottom: 15px;
            }
            h1 {
                font-weight: 800;
                font-size: 2.5rem;
                margin-bottom: 10px;
            }
            .subtitle {
                font-size: 1.1rem;
                opacity: 0.9;
                max-width: 600px;
                margin: 0 auto;
            }
            .navigation {
                display: flex;
                justify-content: center;
                gap: 15px;
                margin-top: 25px;
                flex-wrap: wrap;
            }
            .nav-link {
                background: rgba(255, 255, 255, 0.2);
                color: white;
                padding: 8px 20px;
                border-radius: 20px;
                text-decoration: none;
                font-weight: 600;
                transition: all 0.2s;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .nav-link:hover, .nav-link.active {
                background: white;
                color: var(--primary);
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            }
            main {
                max-width: 1000px;
                margin: 40px auto 0;
                padding: 0 20px;
            }
            .grid {
                display: grid;
                grid-template-columns: 1fr;
                gap: 30px;
            }
            .card {
                background: var(--card-bg);
                border-radius: 20px;
                padding: 30px;
                border: 1px solid var(--border);
                box-shadow: 0 10px 30px rgba(0,0,0,0.02);
            }
            .alert-info {
                background-color: var(--primary-bg);
                border-left: 5px solid var(--primary);
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 25px;
            }
            .alert-info p {
                font-size: 0.95rem;
                color: var(--dark);
            }
            .btn {
                display: inline-block;
                background: var(--primary);
                color: white;
                padding: 12px 35px;
                border-radius: 30px;
                text-decoration: none;
                font-weight: 600;
                margin-top: 15px;
                box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
                transition: all 0.2s;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(74, 144, 226, 0.4);
            }
            .code-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                border-bottom: 1px solid var(--border);
                padding-bottom: 10px;
            }
            .code-title {
                font-weight: 600;
                color: var(--gray);
            }
            pre {
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.9rem;
                background: #0F172A;
                color: #E2E8F0;
                padding: 20px;
                border-radius: 10px;
                overflow-x: auto;
                max-height: 500px;
                border: 1px solid #1E293B;
            }
            footer {
                text-align: center;
                margin-top: 50px;
                color: var(--gray);
                font-size: 0.9rem;
            }
        </style>
    </head>
    <body>
        <header>
            <div class="header-content">
                <div class="emoji">{{ meta['emoji'] }}</div>
                <h1>{{ meta['title'] }}</h1>
                <p class="subtitle">{{ meta['description'] }}</p>
                <div class="navigation">
                    <a href="/" class="nav-link {% if page_key == 'app' %}active{% endif %}">🧸 Main Hub</a>
                    <a href="/kids" class="nav-link {% if page_key == 'kids' %}active{% endif %}">🎒 Kids Playroom</a>
                    <a href="/parent" class="nav-link {% if page_key == 'parent' %}active{% endif %}">🔐 Parent Panel</a>
                    <a href="/db_explorer" class="nav-link {% if page_key == 'db_explorer' %}active{% endif %}">🔍 DB Explorer</a>
                </div>
            </div>
        </header>
        
        <main>
            <div class="grid">
                <div class="card">
                    <div class="alert-info">
                        <p><strong>☁️ Serverless Runtime Information:</strong></p>
                        <p style="margin-top: 5px;">
                            This component runs a persistent Streamlit dashboard using WebSockets and thread-safe database models.
                            Because Vercel executes Python in a stateless, serverless container, the interactive application is hosted on Streamlit Cloud to guarantee full functionality.
                        </p>
                    </div>
                    <h2>Launch Live Interactive Interface</h2>
                    <p style="color: var(--gray); margin-top: 5px; margin-bottom: 15px;">
                        Click the button below to launch the live running deployment of <code>{{ meta['file_path'] }}</code> on the cloud container.
                    </p>
                    <a href="{{ meta['streamlit_url'] }}" target="_blank" class="btn">🚀 Launch Live App</a>
                </div>
                
                <div class="card">
                    <div class="code-header">
                        <span class="code-title">📄 Source Code: <code>{{ meta['file_path'] }}</code></span>
                    </div>
                    <pre><code>{{ code_content }}</code></pre>
                </div>
            </div>
        </main>
        
        <footer>
            <p>Barnaby's Magic English Adventure &copy; 2026</p>
        </footer>
    </body>
    </html>
    """
    return render_template_string(html_template, meta=meta, page_key=page_key, code_content=code_content)

@app.route('/')
def main_hub():
    return render_page("app")

@app.route('/app')
def main_app():
    return render_page("app")

@app.route('/kids')
def kids_playroom():
    return render_page("kids")

@app.route('/parent')
def parent_panel():
    return render_page("parent")

@app.route('/db_explorer')
def db_explorer():
    return render_page("db_explorer")
