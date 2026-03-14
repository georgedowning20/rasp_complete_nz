#!/bin/bash

# Web-based command execution script
# This will run a simple HTTP server that accepts commands via HTTP POST

# Create a simple Python web server for command execution
cat > /tmp/web_terminal.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import subprocess
import json
import urllib.parse
from http import HTTPStatus

class CommandHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/exec':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                command = data.get('command', '')
                
                if command:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                    response_data = {
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'returncode': result.returncode,
                        'command': command
                    }
                else:
                    response_data = {'error': 'No command provided'}
                    
            except Exception as e:
                response_data = {'error': str(e)}
            
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data, indent=2).encode('utf-8'))
            
        elif self.path == '/':
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>RASP Container Terminal</title></head>
            <body>
                <h1>RASP Container Web Terminal</h1>
                <input type="text" id="command" placeholder="Enter command" style="width: 300px;">
                <button onclick="executeCommand()">Execute</button>
                <pre id="output"></pre>
                <script>
                    function executeCommand() {
                        const command = document.getElementById('command').value;
                        fetch('/exec', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({command: command})
                        })
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('output').innerText = JSON.stringify(data, null, 2);
                        });
                    }
                    document.getElementById('command').addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') executeCommand();
                    });
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        else:
            super().do_POST()

PORT = 8080
with socketserver.TCPServer(("", PORT), CommandHandler) as httpd:
    print(f"Web terminal server running on port {PORT}")
    print(f"Access via: http://<container-ip>:{PORT}")
    httpd.serve_forever()
EOF

python3 /tmp/web_terminal.py