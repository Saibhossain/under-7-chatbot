from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Barnaby's Magic English Adventure</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f7f9fc;
                color: #333;
                text-align: center;
                padding: 50px 20px;
            }
            .card {
                background: white;
                border-radius: 20px;
                padding: 40px;
                max-width: 600px;
                margin: 0 auto;
                box-shadow: 0 10px 30px rgba(0,0,0,0.05);
            }
            h1 {
                color: #4A90E2;
                margin-bottom: 10px;
            }
            .emoji {
                font-size: 80px;
                margin-bottom: 20px;
            }
            p {
                font-size: 18px;
                line-height: 1.6;
                color: #666;
            }
            .btn {
                display: inline-block;
                background: #4A90E2;
                color: white;
                padding: 12px 30px;
                border-radius: 30px;
                text-decoration: none;
                font-weight: bold;
                margin-top: 25px;
                box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
                transition: transform 0.2s;
            }
            .btn:hover {
                transform: scale(1.05);
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="emoji">🧸</div>
            <h1>Barnaby the Bear</h1>
            <p>Welcome to Barnaby's Magic English Adventure!</p>
            <p>
                This Streamlit application is designed to run on a persistent server with WebSocket support. 
                Because Vercel runs Python in a stateless, serverless environment, Streamlit cannot run natively here.
            </p>
            <p>
                To play with Barnaby, please deploy this repository to <strong>Streamlit Community Cloud</strong> or <strong>Render</strong>.
            </p>
            <a href="https://share.streamlit.io/" target="_blank" class="btn">Deploy to Streamlit Cloud</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)
