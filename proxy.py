#!/usr/bin/env python3
from flask import Flask, request, Response, jsonify
import requests
import json
from datetime import datetime
from collections import defaultdict
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import os

app = Flask(__name__)

# Email configuration - Add your details here
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",  # For Gmail
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",  # Your email
    "sender_password": "your-app-password",   # Gmail app password
    "recipient_emails": [
        "recipient1@example.com",
        "recipient2@example.com"  # Add multiple recipients
    ]
}

# In-memory analytics storage
analytics_data = {
    "visitors": defaultdict(int),
    "downloads": [],
    "packages": defaultdict(int),
    "start_time": datetime.now().isoformat()
}

def log_request(path, ip, user_agent):
    """Log request for analytics"""
    timestamp = datetime.now().isoformat()
    
    # Count unique visitors (simplified)
    analytics_data["visitors"][ip] += 1
    
    # Log downloads (when accessing blobs/manifests)
    if '/blobs/' in path or '/manifests/' in path:
        parts = path.split('/')
        if len(parts) >= 2:
            package = f"{parts[0]}/{parts[1]}"
            analytics_data["packages"][package] += 1
            analytics_data["downloads"].append({
                "package": package,
                "timestamp": timestamp,
                "ip": ip[:8] + "****"  # Partial IP for privacy
            })
    
    print(f"📊 {timestamp} | {ip} | {user_agent[:50]} | /{path}")

def send_analytics_email():
    """Send analytics report via email"""
    try:
        total_visitors = len(analytics_data["visitors"])
        total_requests = sum(analytics_data["visitors"].values())
        total_downloads = len(analytics_data["downloads"])
        
        # Create email content
        subject = f"📊 GHCR Proxy Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"""
        <html>
        <body>
            <h2>📊 GHCR Proxy Analytics Report</h2>
            <p><strong>Report Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h3>📈 Summary</h3>
            <ul>
                <li><strong>Unique Visitors:</strong> {total_visitors}</li>
                <li><strong>Total Requests:</strong> {total_requests}</li>
                <li><strong>Package Downloads:</strong> {total_downloads}</li>
            </ul>
            
            <h3>📦 Top Packages</h3>
            <ul>
        """
        
        # Add top packages
        for pkg, count in sorted(analytics_data["packages"].items(), key=lambda x: x[1], reverse=True)[:5]:
            body += f"<li><strong>{pkg}:</strong> {count} downloads</li>"
        
        body += """
            </ul>
            
            <h3>🕐 Recent Downloads</h3>
            <ul>
        """
        
        # Add recent downloads
        for download in analytics_data["downloads"][-5:][::-1]:
            body += f"<li>{download['timestamp'][:19]} - {download['package']} from {download['ip']}</li>"
        
        body += """
            </ul>
        </body>
        </html>
        """
        
        # Send email to all recipients
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_CONFIG["sender_email"]
        msg['To'] = ", ".join(EMAIL_CONFIG["recipient_emails"])
        
        html_part = MIMEText(body, 'html')
        msg.attach(html_part)
        
        # Send via SMTP
        with smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"]) as server:
            server.starttls()
            server.login(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["sender_password"])
            server.send_message(msg)
        
        print(f"📧 Analytics email sent to {len(EMAIL_CONFIG['recipient_emails'])} recipients")
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def schedule_emails():
    """Schedule daily email reports"""
    schedule.every().day.at("09:00").do(send_analytics_email)  # Daily at 9 AM
    # schedule.every().hour.do(send_analytics_email)  # Uncomment for hourly
    
    while True:
        schedule.run_pending()
        time.sleep(60)

@app.route('/v2/', defaults={'path': ''})
@app.route('/v2/<path:path>')
def proxy_registry(path):
    """Proxy Docker registry requests to GHCR"""
    
    # Get client info
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    # Log for analytics
    log_request(path, ip, user_agent)
    
    # Proxy to GHCR
    target_url = f"https://ghcr.io/v2/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
    
    try:
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            allow_redirects=False,
            timeout=30
        )
        
        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        print(f"❌ Proxy error: {e}")
        return Response(f"Proxy error: {str(e)}", status=500)

@app.route('/analytics')
def get_analytics():
    """Get analytics dashboard"""
    
    total_visitors = len(analytics_data["visitors"])
    total_requests = sum(analytics_data["visitors"].values())
    total_downloads = len(analytics_data["downloads"])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GHCR Proxy Analytics</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .stat {{ display: inline-block; margin: 10px 20px; text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #0366d6; }}
            .stat-label {{ color: #666; }}
            .package {{ padding: 10px; border-left: 4px solid #0366d6; margin: 10px 0; background: #f8f9fa; }}
        </style>
    </head>
    <body>
        <h1>📊 GHCR Proxy Analytics</h1>
        
        <div class="card">
            <h2>📈 Overview</h2>
            <div class="stat">
                <div class="stat-number">{total_visitors}</div>
                <div class="stat-label">Unique Visitors</div>
            </div>
            <div class="stat">
                <div class="stat-number">{total_requests}</div>
                <div class="stat-label">Total Requests</div>
            </div>
            <div class="stat">
                <div class="stat-number">{total_downloads}</div>
                <div class="stat-label">Package Downloads</div>
            </div>
        </div>
        
        <div class="card">
            <h2>📦 Popular Packages</h2>
            {"".join(f'<div class="package"><strong>{pkg}</strong>: {count} downloads</div>' 
                    for pkg, count in sorted(analytics_data["packages"].items(), key=lambda x: x[1], reverse=True)[:10])}
        </div>
        
        <div class="card">
            <h2>🕐 Recent Downloads</h2>
            {"".join(f'<div style="margin: 5px 0;"><code>{d["timestamp"][:19]}</code> - {d["package"]} from {d["ip"]}</div>' 
                    for d in analytics_data["downloads"][-10:][::-1])}
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/send-report')
def send_report_now():
    """Manually trigger email report"""
    send_analytics_email()
    return jsonify({"status": "Email sent!", "timestamp": datetime.now().isoformat()})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "uptime": datetime.now().isoformat()})

@app.route('/')
def home():
    return f"""
    <h1>🐳 GHCR Analytics Proxy</h1>
    <p><strong>Usage:</strong></p>
    <pre>docker pull {request.host}/username/package-name</pre>
    <p><a href="/analytics">📊 View Analytics</a></p>
    <p><a href="/send-report">📧 Send Email Report Now</a></p>
    <p><a href="/health">🏥 Health Check</a></p>
    """

if __name__ == '__main__':
    print("🚀 Starting GHCR Analytics Proxy...")
    print("📊 Analytics will be available at /analytics")
    print("📧 Email reports will be sent daily at 9 AM")
    
    # Start email scheduler in background
    email_thread = threading.Thread(target=schedule_emails, daemon=True)
    email_thread.start()
    
    app.run(host='0.0.0.0', port=8000, debug=True)
