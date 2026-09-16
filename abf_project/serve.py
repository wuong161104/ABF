import http.server
import webbrowser
import threading
import time
import os
import sys

PORT = 3000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class DualHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def open_browser():
    time.sleep(1.2)
    url = f"http://127.0.0.1:{PORT}"
    print(f"[*] Dang tu dong mo: {url}")
    webbrowser.open(url)

def main():
    os.chdir(DIRECTORY)
    
    print("=" * 60)
    print("          ABF EXECUTIVE DASHBOARD SERVER")
    print("=" * 60)
    print(f"[*] Thu muc web: {DIRECTORY}")
    print(f"[*] Server URL:   http://127.0.0.1:{PORT}")
    print("------------------------------------------------------------")
    print("[+] Ban co the dong cua so Antigravity ma khong bi mat web.")
    print("[+] De dung server: Dong cua so den nay hoac bam Ctrl + C.")
    print("=" * 60)

    # Start browser in background
    threading.Thread(target=open_browser, daemon=True).start()

    server_address = ("127.0.0.1", PORT)
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer(server_address, DualHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[!] Server da dung.")

if __name__ == "__main__":
    main()
