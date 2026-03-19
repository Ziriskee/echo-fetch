import http.server
import json
import tkinter as tk

class APIServerHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, ui_instance=None, **kwargs):
        self.ui_instance = ui_instance
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length'))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            if data.get('action') == 'add_download':
                url = data.get('url', '')
                filename = data.get('filename', '')
                
                # Send response back to extension
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "queued"}).encode())
                
                # Safely dispatch to main thread via UI instance
                if self.ui_instance and self.ui_instance.winfo_exists():
                    self.ui_instance.after(0, 
                        lambda: self.ui_instance._handle_browser_download(url, filename))
                else:
                    print("Warning: UI instance not available")
            else:
                self.send_response(400)
                self.end_headers()
        
        except Exception as e:
            print(f"API Error: {e}")
            self.send_error(500)
    
    def log_message(self, format, *args):
        pass  # Silence server logs
