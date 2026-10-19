import socket, threading, select
def fwd(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data: break
            dst.sendall(data)
    except OSError: pass
    finally:
        try: dst.shutdown(socket.SHUT_WR)
        except OSError: pass
def handle(client):
    try:
        up = socket.create_connection(("127.0.0.1", 9222), timeout=5)
        up.settimeout(None)
    except OSError:
        client.close(); return
    t1 = threading.Thread(target=fwd, args=(client, up), daemon=True)
    t2 = threading.Thread(target=fwd, args=(up, client), daemon=True)
    t1.start(); t2.start(); t1.join(); t2.join()
    client.close(); up.close()
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 9223)); s.listen(16)
while True:
    c, _ = s.accept()
    threading.Thread(target=handle, args=(c,), daemon=True).start()
