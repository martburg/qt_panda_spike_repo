import socket
import time

REMOTE = ("127.0.0.11", 15001)  # adjust to one of your sim endpoints
TIMEOUT_S = 1.0

# Minimal downlink line (must match what your sim expects)
# If your sim parses by index, keep enough ';' fields.
# This example is: LifetickUIrx; ... ; ControlIN ; ... ; SpeedSollIN ; ...
down = "1;0;0;0;0;1;0;0.0;0;0;" + ("0;" * 40)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT_S)

sock.sendto(down.encode("utf-8"), REMOTE)
data, addr = sock.recvfrom(65535)

print("from", addr)
print(data.decode("utf-8", errors="replace")[:400])
