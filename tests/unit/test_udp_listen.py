import socket
import threading
import time

from steuerung3d.tools.udp_listen import decode_datagram, listen_once


def _free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_decode_datagram_json():
    dd = decode_datagram(b'{"axes":[0.1, -0.2], "buttons":[0,1]}')
    assert dd.json_obj is not None
    assert dd.json_obj["axes"][0] == 0.1


def test_decode_datagram_non_json():
    dd = decode_datagram(b"hello world")
    assert dd.json_obj is None
    assert "hello world" in dd.text


def test_listen_once_receives_packet():
    port = _free_udp_port()

    def sender():
        time.sleep(0.05)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(b'{"ping": 1}', ("127.0.0.1", port))
        s.close()

    t = threading.Thread(target=sender, daemon=True)
    t.start()

    dd, addr = listen_once("127.0.0.1", port, timeout_s=1.0)
    assert dd.json_obj is not None
    assert dd.json_obj["ping"] == 1
    assert addr[0] == "127.0.0.1"
