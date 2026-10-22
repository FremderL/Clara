import socket

def show_viernes():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 9876))
        sock.send(b"SHOW")
        sock.close()
    except:
        print("Viernes no esta en ejecucion")

if __name__ == "__main__":
    show_viernes()