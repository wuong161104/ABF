import time
import sys
from pyngrok import ngrok, conf

def start_tunnel(port=5678):
    print("=" * 60)
    print(f"   Dang khoi dong Ngrok Tunnel cho n8n (Port {port})...")
    print("=" * 60)
    
    try:
        tunnel = ngrok.connect(port, "http")
        print("\n" + "=" * 60)
        print(f" [THANH CONG] NGROK DANG HOAT DONG!")
        print(f" Public URL -> {tunnel.public_url}")
        print(f" Forwarding to: http://localhost:{port}")
        print("=" * 60)
        print("\n[!] Nhan Ctrl + C de dung tunnel.\n")
        
        # Giu tien trinh chay lien tuc
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nDang tat Ngrok tunnel...")
        ngrok.kill()
        print("Da tat.")
    except Exception as e:
        print(f"\n[Loi]: {e}")
        input("\nNhan Enter de thoat...")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5678
    start_tunnel(port)
