
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler

class HealthHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves static files from 'public' directory
    and responds to /api/health with JSON status."""
    
    # Serve files from the 'public' directory
    directory = 'public'

    def do_GET(self):
        if self.path == '/api/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({"status": "ok"}).encode('utf-8')
            self.wfile.write(response)
        else:
            # Let the parent class handle static file serving
            super().do_GET()

if __name__ == "__main__":
    server_address = ('', 8999)
    httpd = HTTPServer(server_address, HealthHandler)
    print(f"Serving on port {server_address[1]}...")
    httpd.serve_forever()
