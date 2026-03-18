from .QtWidgets import QWidget
from .QtCore import QFile

class QUiLoader:
    def load(self, file: QFile, parent: QWidget | None = ...) -> QWidget: ...
