# save as sniff_uplink.py and run: python sniff_uplink.py
import socket
from steuerung3d.protocol.legacy_plc import parse_uplink

HOST, PORT = "127.0.0.1", 52020  # <- whichever port your UDP uplink arrives on
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
print("listening", (HOST, PORT))

while True:
    data, addr = sock.recvfrom(8192)
    s = data.decode("utf-8", "replace")
    up = parse_uplink(s)
    lt = up.fields.get("LifetickUItx")
    st = up.tail.get("SystemTime")
    print(f"from {addr}  LifetickUItx={lt!r}  SystemTime={st!r}")
