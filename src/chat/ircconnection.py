from PyQt5.QtCore import QObject, QSocketNotifier, QTimer, pyqtSignal
import logging
import sys

import chat
from chat import irclib
from chat.irclib import SimpleIRCClient
from chat.chatline import ServerMessage, ChatLine, ChatLineTypes
from chat.channel2 import ChannelID, ChannelType
import util
import re
import time

logger = logging.getLogger(__name__)
PONG_INTERVAL = 60000  # milliseconds between pongs


class IrcCredentials:
    def __init__(self, creds, me):
        self._creds = creds
        self._me = me

    @property
    def password(self):
        return self._creds.password

    @property
    def login(self):
        return self._creds.login

    @property
    def username(self):
        if self._me.player is None:
            return self._creds.login
        return self._me.player.login


class ChatterInfo:
    def __init__(self, name, hostname, elevation):
        self.name = name
        self.hostname = hostname
        self.elevation = elevation


class IrcSignals(QObject):
    new_line = pyqtSignal(object)
    new_server_message = pyqtSignal(object)
    new_channel_chatters = pyqtSignal(str, list)
    channel_chatters_left = pyqtSignal(str, list)
    chatters_quit = pyqtSignal(list)
    quit_channel = pyqtSignal(str)
    chatter_renamed = pyqtSignal()
    new_chatter_elevation = pyqtSignal(str, object, str, str)
    new_channel_topic = pyqtSignal(str, str)
    disconnected = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)


class IrcConnection(IrcSignals, SimpleIRCClient):

    def __init__(self, host, port, irc_creds, ssl=False):
        IrcSignals.__init__(self)
        SimpleIRCClient.__init__(self)

        self.host = host
        self.port = port
        self.ssl = ssl
        self.creds = irc_creds

        self._notifier = None
        self._timer = QTimer()
        self._timer.timeout.connect(self.once)

        self._nickserv_registered = False
        self._identified = False

    def disconnect(self):
        self.irc_disconnect()
        if self._notifier is not None:
            self._notifier.activated.disconnect(self.once)
            self._notifier = None

    def connect(self, nick, username):
        logger.info("Connecting to IRC at: {}:{}. TLS: {}".format(
            self.irc_host, self.irc_port, self.irc_tls))
        try:
            self.irc_connect(self.host, self.port, nick, ssl=self.ssl,
                             ircname=nick, username=username)
            self._notifier = QSocketNotifier(
                    self.ircobj.connections[0]._get_socket().fileno(),
                    QSocketNotifier.Read,
                    self)
            self._notifier.activated.connect(self.once)
            self._timer.start(PONG_INTERVAL)
            return True
        except:
            logger.debug("Unable to connect to IRC server.")
            logger.error("IRC Exception", exc_info=sys.exc_info())
            return False

    def is_connected(self):
        return self.connection.is_connected()

    def _only_if_connected(fn):
        def _if_connected(self, *args, **kwargs):
            if not self.connection.is_connected():
                return False
            fn(self, *args, **kwargs)
            return True
        return _if_connected

    @_only_if_connected
    def set_topic(self, channel, topic):
        self.connection.topic(channel, topic)

    @_only_if_connected
    def send_message(self, target, text):
        self.connection.privmsg(target, text)

    @_only_if_connected
    def send_action(self, target, text):
        self.connection.action(target, text)

    @_only_if_connected
    def join(self, channel):
        self.connection.join(channel)

    def _log_event(self, e):
        text = '\n'.join(e.arguments())
        msg = ServerMessage(e.eventtype(), e.source(), e.target(), text)
        self.new_server_message.emit(msg)

    def _log_client_message(self, text):
        msg = ServerMessage('client_message', 'client', 'server', text)
        self.new_server_message.emit(msg)

    def on_welcome(self, c, e):
        self._log_event(e)

    def _send_nickserv_creds(self, fmt):
        self._log_client_message(fmt.format(self.creds.login,
                                            '[password_hash]'))

        msg = fmt.format(self.creds.login, util.md5text(self.creds.password))
        self.connection.privmsg('NickServ', msg)

    def _nickserv_identify(self):
        if self._identified:
            return
        self._send_nickserv_creds('identify {} {}')

    def _nickserv_register(self):
        if self._nickserv_registered:
            return
        self._send_nickserv_creds('register {} {}@users.faforever.com')
        self._nickserv_registered = True

    def on_identified(self):
        if self.connection.get_nickname != self.creds.nickname:
            self._send_nickserv_creds('recover {} {}')

    def on_version(self, c, e):
        msg = "Forged Alliance Forever " + util.VERSION_STRING
        self.connection.privmsg(e.source(), msg)

    def on_motd(self, c, e):
        self._log_event(e)
        self._nickserv_identify()

    def on_endofmotd(self, c, e):
        self._log_event(e)

    def on_namreply(self, c, e):
        self._log_event(e)
        channel = e.arguments()[1]
        listing = e.arguments()[2].split()

        def userdata(data):
            name = data.strip(chat.IRC_ELEVATION)
            elevation = data[0] if data[0] in chat.IRC_ELEVATION else None
            hostname = ''
            return ChatterInfo(name, hostname, elevation)

        chatters = [userdata(user) for user in listing]
        self.new_channel_chatters.emit(channel, chatters)

    def on_whoisuser(self, c, e):
        self._log_event(e)

    def _event_to_chatter(self, e):
        name, _id, elevation, hostname = chat.parse_irc_source(e.source)
        return ChatterInfo(name, hostname, elevation)

    def on_join(self, c, e):
        channel = e.target()
        chatter = self._event_to_chatter(e)
        self.new_channel_chatters.emit(channel, [chatter])

    def on_part(self, c, e):
        channel = e.target()
        chatter = self._event_to_chatter(e)
        self.channel_chatters_left.emit(channel, chatter)
        if chatter.name == self.creds.username:
            self.quit_channel.emit(channel)

    def on_quit(self, c, e):
        chatter = self._event_to_chatter(e)
        self.chatters_quit.emit([chatter])

    def on_nick(self, c, e):
        oldnick = chat.user2name(e.source())
        newnick = e.target()

        self.chatter_renamed(oldnick, newnick)
        self._log_event(e)

    def on_mode(self, c, e):
        if len(e.arguments()) < 2:
            return

        name, _, elevation, hostname = chat.parse_irc_source(e.arguments()[1])
        chatter = ChatterInfo(name, hostname, elevation)
        modes = e.arguments()[0]
        channel = e.target()
        added, removed = self._parse_elevation(modes)
        self.new_chatter_elevation.emit(channel, chatter,
                                        added, removed)

    def _parse_elevation(self, modes):
        add = re.compile(".*\+([a-z]+)")
        remove = re.compile(".*\-([a-z]+)")
        mode_to_elevation = {"o": "Q", "q": "~", "v": "+"}

        def get_elevations(expr):
            match = re.search(expr, modes)
            if not match:
                return ""
            match = match.group(1)
            return ''.join(mode_to_elevation[c] for c in match)

        return get_elevations(add), get_elevations(remove)

    def on_umode(self, c, e):
        self._log_event(e)

    def on_notice(self, c, e):
        self._log_event(e)

    def on_topic(self, c, e):
        channel = e.target()
        announcement = " ".join(e.arguments())
        self.new_channel_topic.emit(channel, announcement)

    def on_currenttopic(self, c, e):
        channel = e.arguments()[0]
        announcement = " ".join(e.arguments()[1:])
        self.new_channel_topic.emit(channel, announcement)

    def on_topicinfo(self, c, e):
        self._log_event(e)

    def on_list(self, c, e):
        self._log_event(e)

    def on_bannedfromchan(self, c, e):
        self._log_event(e)

    def _emit_line(self, chatter, target, text, line_type, channel_type):
        if channel_type == ChannelType.PUBLIC:
            channel_name = target
        else:
            channel_name = chatter.name
        chid = ChannelID(channel_type, channel_name)
        line = ChatLine(line_type, chid, chatter.name,
                        text, time.time())
        self.new_line.emit(line)

    def on_pubmsg(self, c, e):
        chatter = self._event_to_chatter(e)
        channel = e.target()
        text = "\n".join(e.arguments())

        chid = ChannelID(ChannelType.PUBLIC, channel)
        line = ChatLine(ChatLineTypes.MESSAGE, chid, chatter.name,
                        text, time.time())
        self.new_line.emit(line)

    def on_privnotice(self, c, e):
        chatter = self._event_to_chatter(e)
        notice = e.arguments()[0]
        prefix = notice.split(" ")[0]
        target = prefix.strip("[]")

        if chatter.name.lower() == 'nickserv':
            self._handle_nickserv_message(notice)
            return

        text = "\n".join(e.arguments()).lstrip(prefix)
        self._emit_line(chatter, target, text,
                        ChatLineTypes.NOTICE, ChannelType.PRIVATE)

    def _handle_nickserv_message(self, notice):
        if (notice.find("registered under your account") >= 0 or
           notice.find("Password accepted") >= 0):
            if not self._identified:
                self._identified = True
                self.on_identified()
        elif notice.find("isn't registered") >= 0:
            self._nickserv_register()
        elif notice.find("RELEASE") >= 0:
            self.connection.privmsg('release {} {}')
        elif notice.find("hold on") >= 0:
            self.connection.nick(self.creds.nickname)

    def on_disconnect(self, c, e):
        self._identified = False
        self._timer.stop()
        self.disconnected.emit()

    def on_privmsg(self, c, e):
        chatter = self._event_to_chatter(e)
        text = "\n".join(e.arguments())
        self._emit_line(chatter, None, text,
                        ChatLineTypes.MESSAGE, ChannelType.PRIVATE)

    def on_action(self, c, e):
        chatter = self._event_to_chatter(e)
        target = e.target()
        text = "\n".join(e.arguments())
        chtype = (ChannelType.PUBLIC if irclib.is_channel(target)
                  else ChannelType.PRIVATE)
        self._emit_line(chatter, target, text,
                        ChatLineTypes.MESSAGE, chtype)

    def on_nosuchnick(self, c, e):
        self._nickserv_register()

    def on_default(self, c, e):
        self._log_event(e)
        if "Nickname is already in use." in "\n".join(e.arguments()):
            self.connection.nick(self.creds.nickname + "_")

    def on_kick(self, c, e):
        pass
