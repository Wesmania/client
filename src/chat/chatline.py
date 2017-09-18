from enum import Enum
from chat.avatar import Avatar


class ChatLineTypes(Enum):
    MESSAGE = "message"
    NOTICE = "notice"
    ACTION = "action"
    ANNOUNCEMENT = "announcement"
    RAW = "raw"


class ChatLine:
    def __init__(self, kind, channel, sender, text, time):
        self.kind = kind
        self.channel = channel
        self.sender = sender
        self.text = text
        self.time = time
        self.metadata = None

    def from_chatter(self):
        return self.kind in [ChatLineTypes.MESSAGE, ChatLineTypes.ACTION]


class ChatLineMetadata:
    def __init__(self):
        self.chatter = None
        self.player = None
        self.mentions_me = False


class ChatLineChatterMetadata:
    def __init__(self):
        self.is_friend = False
        self.is_foe = False
        self.is_mod = False


class ChatLinePlayerMetadata:
    def __init__(self):
        self.avatar = None
        self.is_clannie = False


class ChatLineMetadataFiller:
    def __init__(self, chatterset, me):
        self._chatterset = chatterset
        self._me = me

    def fill_metadata(self, line):
        data = ChatLineMetadata()
        data.mentions_me = self._mentions_me(line)

        if line.from_chatter():
            data.chatter = self._chatter_metadata(line)
            data.player = self._player_metadata(line)

        line.metadata = data

    def _mentions_me(self, line):
        if self._me.player is None:
            return False
        return line.text.find(self._me.player.login) != -1

    def _get_chatter(self, line):
        return self._chatterset.get(line.sender)

    def _chatter_metadata(self, line):
        chatter = self._get_chatter(line)
        if chatter is None:
            return None
        player_id = -1 if chatter.player is None else chatter.player.id

        meta = ChatLineChatterMetadata()

        meta.is_friend = self._me.isFriend(player_id, chatter.name)
        meta.is_foe = self._me.isFoe(player_id, chatter.name)
        meta.is_mod = chatter.is_mod(line.channel)
        return meta

    def _player_metadata(self, line):
        chatter = self._get_chatter(line)
        if chatter is None or chatter.player is None:
            return None
        player = chatter.player

        meta = ChatLinePlayerMetadata()
        meta.is_clannie = self._me.isClannie(player.id)
        avatar = player.avatar["url"]
        avatarTip = player.avatar["tooltip"]
        meta.avatar = Avatar(avatar, avatarTip)
        return meta


class ServerMessage:
    def __init__(self, eventtype, sender, target, text):
        self.eventtype = eventtype
        self.sender = sender
        self.target = target
        self.text = text
