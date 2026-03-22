from qt_panda_spike.backends.base import FrameImage
from qt_panda_spike.backends.native_embed import NativeEmbedBackend
from qt_panda_spike.backends.offscreen import OffscreenBackend


def test_imports() -> None:
    assert FrameImage(1, 1, b"\x00\x00\x00\x00").width == 1
    assert NativeEmbedBackend() is not None
    assert OffscreenBackend() is not None
