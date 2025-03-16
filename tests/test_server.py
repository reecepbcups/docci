
import http.server
import socket
import threading
import time


class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Hello, world!')

class MyServer():
    server: http.server.HTTPServer
    port: int

    def __init__(self, port: int = 0):
        self.server = http.server.HTTPServer(('localhost', port), MyHandler)
        self.port = self.server.server_address[1]

    @staticmethod
    def get_free_port():
        """
        Returns a free port on the local machine
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))  # Binding to port 0 lets the OS assign a free port
        port = s.getsockname()[1]  # Get the assigned port number
        s.close()
        return port

    def start_server(self):
        time.sleep(1)
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()
