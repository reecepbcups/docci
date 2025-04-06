

# This file is used as a demo for the main README.md examples
# Docci testing docci docs

import http.server
import platform
import socketserver
import sys
import threading
from logging import getLogger
from urllib.parse import urlparse


def main():
    if len(sys.argv) == 0:
        getLogger(__name__).error("Error: No arguments provided")
        return

    if sys.argv[1] == "web-server":
        port = 3000
        if len(sys.argv) > 2 and sys.argv[2] == "--port":
            port = int(sys.argv[3])

        long_running_process(port)

def long_running_process(port=3000):
    import socket
    import time

    # Set the socket to allow address reuse before creating the server
    socketserver.TCPServer.allow_reuse_address = True

    class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed_path = urlparse(self.path)

            if parsed_path.path == "/health":
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'HEALTH GOOD')
                return
            elif parsed_path.path == "/kill":
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Server shutting down...")

                # Use a separate thread to stop the server without deadlock
                def shutdown_server():
                    time.sleep(0.5)  # Give time for response to be sent
                    httpd.shutdown()
                    httpd.server_close()

                threading.Thread(target=shutdown_server).start()
                return

            return super().do_GET()

        def log_message(self, format, *args):
            return

    print(f"Server started at http://localhost:{port}")

    # Check if port is already in use and attempt to force close it
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()

        if result == 0:  # Port is in use
            print(f"Port {port} is in use. Attempting to force close it...")
            # Force close the port - OS specific approach

            if platform.system() == "Linux" or platform.system() == "Darwin":
                import os
                os.system(f"kill -9 $(lsof -t -i:{port})")
                time.sleep(1)  # Wait for port to be released
    except:
        pass

    try:
        httpd = socketserver.TCPServer(("", port), HealthCheckHandler)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server")
        finally:
            httpd.shutdown()
            httpd.server_close()

            # Double-check that the port is released
            print(f"Ensuring port {port} is fully released...")
            time.sleep(0.25)  # Give the OS time to release the port

            # Set SO_REUSEADDR on the socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('', port))
                print(f"Port {port} successfully released")
                s.close()
            except OSError:
                print(f"Port {port} still in use, trying force release")
                # Try force release again
                if platform.system() == "Linux" or platform.system() == "Darwin":
                    os.system(f"kill -9 $(lsof -t -i:{port})")
                s.close()

    except OSError as e:
        print(f"Error: Port {port} is already in use. {e}")
        print("Port is in use. Attempting to force close it...")
        if platform.system() == "Linux" or platform.system() == "Darwin":
            os.system(f"kill -9 $(lsof -t -i:{port})")


if __name__ == "__main__":
    main()
