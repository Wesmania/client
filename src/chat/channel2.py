from enum import Enum
from PyQt.QtCore import QObject, pyqtSignal


class ChannelType(Enum):
    PUBLIC = 1
    PRIVATE = 2


class ChannelID:
    def __init__(self, type_, name):
        self.type = type_
        self.name = name


class Lines(QObject):
    new_line = pyqtSignal(object)
    lines_removed = pyqtSignal(int, int)

    def __init__(self):
        QObject.__init__(self)
        self._lines = []

    def __iter__(self):
        return iter(self._lines)

    def add_line(self, line):
        self._lines.append(line)
        self.new_line.emit(line)

    def remove_lines(self, number, offset=0):
        number = min(number, len(self._lines) - offset)
        del self._lines[offset:offset + number]
        self.lines_removed.emit(number, offset)


class Channel(Lines):
    new_topic = pyqtSignal(str)

    def __init__(self, info):
        Lines.__init__(self)
        self.info = info
        self._topic = ""

    @property
    def topic(self):
        return self._topic

    @topic.setter
    def topic(self, topic):
        self._topic = topic
        self.new_topic.emit(topic)


class ServerMessages(Lines):
    def __init__(self):
        Lines.__init__(self)
