from PyQt5.QtCore import QObject, pyqtSignal
from chat.channel2 import Channel, ServerMessages


class Chat(QObject):
    new_line = pyqtSignal(object)
    channel_added = pyqtSignal(object, object)
    channel_removed = pyqtSignal(object, object)

    def __init__(self, chatterset, metadata_filler):
        QObject.__init__(self)
        self._chatterset = chatterset
        self._metadata_filler = metadata_filler
        self.channels = {}
        self.server_messages = ServerMessages()

    def add_channel(self, cid):
        if cid in self.channels:
            raise ValueError

        channel = Channel(cid)
        self.channels[cid] = channel
        self.channel_added.emit(channel)

    def remove_channel(self, cid):
        if cid not in self.channels:
            raise IndexError

        channel = self.channels[cid]
        del self.channels[cid]
        self.channel_removed.emit(channel)

    def add_line(self, line):
        if line.channel not in self.channels:
            raise ValueError

        self._metadata_filler.fill_metadata(line)
        self.channels[line.channel].add_line(line)
        self.new_line.emit(line)

    def add_server_message(self, message):
        self.server_messages.add_line(message)
