# save as sniff_telem.py and run: python sniff_telem.py
import json
import socket

HOST, PORT = "127.0.0.1", 51002  # <- HIP telemetry port
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
print("listening", (HOST, PORT))

while True:
    data, addr = sock.recvfrom(65535)
    msg = json.loads(data.decode("utf-8", "replace"))
    if msg.get("kind") != "telemetry":
        continue
    axes = msg["payload"].get("axes", {})
    # print one axis (pick any that exists)
    for k, v in axes.items():
        print(k, "lifetick_tx=", v.get("lifetick_tx"), "timetick_ms=", v.get("timetick_ms"))
        break
