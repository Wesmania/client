from fa.replay import replay

import util
from PyQt5 import QtWidgets, QtCore, QtGui
import time
from chat import logger
from chat.chatter import Chatter
import re
import json
import html

QUERY_BLINK_SPEED = 250
CHAT_TEXT_LIMIT = 350
CHAT_REMOVEBLOCK = 50

FormClass, BaseClass = util.THEME.loadUiType("chat/channel.ui")


class IRCPlayer():
    def __init__(self, name):
        self.name = name
        self.id = -1
        self.clan = None


class Formatters(object):
    FORMATTER_AVATAR         = str(util.THEME.readfile("chat/formatters/avatar.qthtml"))
    FORMATTER_ANNOUNCEMENT   = str(util.THEME.readfile("chat/formatters/announcement.qthtml"))
    FORMATTER_MESSAGE        = str(util.THEME.readfile("chat/formatters/message.qthtml"))
    FORMATTER_ACTION         = str(util.THEME.readfile("chat/formatters/action.qthtml"))
    FORMATTER_RAW            = str(util.THEME.readfile("chat/formatters/raw.qthtml"))
    NICKLIST_COLUMNS         = json.loads(util.THEME.readfile("chat/formatters/nicklist_columns.json"))

    @classmethod
    def format(cls, fmt, avatar, **kwargs):
        if avatar is None:
            avatar_img = ""
        else:
            avatar_img = cls.FORMATTER_AVATAR.format(avatar=avatar, **kwargs)
        return fmt.format(avatar=avatar_img, **kwargs)


# Helper class to schedule single event loop calls.
class ScheduledCall(QtCore.QObject):
    _call = QtCore.pyqtSignal()

    def __init__(self, fn):
        QtCore.QObject.__init__(self)
        self._fn = fn
        self._called = False
        self._call.connect(self._runCall, QtCore.Qt.QueuedConnection)

    def scheduleCall(self):
        if self._called:
            return
        self._called = True
        self._call.emit()

    def _runCall(self):
        self._called = False
        self._fn()


class ChatLog:
    def __init__(self, widget, client):
        self._w = widget
        self._w.anchorClicked.connect(self.openUrl)
        self._client = client

        self.lines = 0
        self.snap_to_bottom_threshold = 20
        self.max_lines = 350
        self.autotrim_block_size = 50

    def addLine(self, text):
        current_distance = self.scrollDistanceFromBottom()
        cursor = self._w.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self._w.setTextCursor(cursor)
        self._w.insertHtml(text)
        self.lines += 1
        self._check_autoscroll(current_distance)
        self._check_autotrim()

    def removeLines(self, number):
        lines_to_remove = min(number, self.lines)
        cursor = self._w.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Start)
        cursor.movePosition(QtGui.QTextCursor.Down,
                            QtGui.QTextCursor.KeepAnchor, lines_to_remove)
        cursor.removeSelectedText()
        self.lines -= lines_to_remove

    def scrollDistanceFromBottom(self):
        scrollbar = self._w.verticalScrollBar()
        return scrollbar.maximum() - scrollbar.value()

    def scrollToBottom(self):
        scrollbar = self._w.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self):
        self._w.setPlainText("")
        self.lines = 0

    def _check_autoscroll(self, old_distance):
        if self.snap_to_bottom_threshold is None:
            return
        if old_distance <= self.snap_to_bottom_threshold:
            self.scrollToBottom()

    def _check_autotrim(self):
        if self.max_lines is None:
            return
        if self.lines > self.max_lines:
            self.removeLines(self.autotrim_block_size)

    def addAvatar(self, name, icon):
        doc = self._w.document()
        name_url = QtCore.QUrl(name)
        if doc.resource(QtGui.QTextDocument.ImageResource, name_url):
            return
        doc.addResource(QtGui.QTextDocument.ImageResource, name_url, icon)

    def openUrl(self, url):
        logger.debug("Clicked on URL: " + url.toString())
        if url.scheme() == "faflive":
            replay(url)
        elif url.scheme() == "fafgame":
            self._client.joinGameFromURL(url)
        else:
            QtGui.QDesktopServices.openUrl(url)

    def copy(self):
        self._w.copy()

    def setTextWidth(self):
        self._w.setLineWrapColumnOrWidth(self._w.size().width() - 20)  # Hardcoded, but seems to be enough (tabstop was a bit large)


class FormattedText:
    """
    Qt has Qfont for that, but it can't be conveniently used with Python's
    string formatting, so let's roll our own.
    """
    def __init__(self, properties={}):
        self.properties = properties

    def copy(self):
        return FormattedText(self.properties.copy())

    def update(self, properties):
        self.properties.update(properties)

    def _css_property(self, name, value):
        name = html.escape(name, True)
        value = html.escape(value, True)
        return "{}='{}';".format(name, value)

    def _css_style(self):
        return "".join(
                self._css_property(n, v) for n, v in self.properties.items())

    def format(self, text):
        return '<p style="{}">{}</p>'.format(self._css_style(), text)


class ChatLineFormat:
    FORMATTER = str(util.THEME.readfile("chat/formatters/chatline.qthtml"))

    def __init__(self, name_format=None, text_format=None, time_format=None):
        self.name_format = (name_format if name_format is not None
                            else FormattedText())
        self.text_format = (text_format if text_format is not None
                            else FormattedText())
        self.time_format = (time_format if time_format is not None
                            else FormattedText())

    def copy(self):
        new = ChatLineFormat()
        new.name_format = self.name_format.copy()
        new.text_format = self.text_format.copy()
        new.time_format = self.time_format.copy()
        return new

    def update(self, fmt):
        if "name" in fmt:
            self.name_format.update(fmt["name"])
        if "text" in fmt:
            self.text_format.update(fmt["text"])
        if "time" in fmt:
            self.time_format.update(fmt["time"])

    def format(self, avatar="", name="", text="", time=""):
        name = self.name_format.format(name)
        text = self.text_format.format(text)
        time = self.time_format.format(time)
        return self.FORMATTER.format(avatar=avatar, name=name, text=text,
                                     time=time)

    @classmethod
    def get_format(cls, name):
        formats_dir = "chat/formatters/formats/{}.json"
        fmt = json.loads(util.THEME.readfile(formats_dir.format(name)))
        return cls(fmt.get["name"], fmt.get["text"], fmt.get["time"])


class Channel(FormClass, BaseClass):
    """
    This is an actual chat channel object, representing an IRC chat room and the users currently present.
    """
    def __init__(self, chat_widget, name, chatterset, me, private=False):
        BaseClass.__init__(self, chat_widget)

        self.setupUi(self)

        # Special HTML formatter used to layout the chat lines written by people
        self.chat_widget = chat_widget
        self.chat_log = ChatLog(self.chatArea, chat_widget.client)
        self.chatters = {}
        self.items = {}
        self._chatterset = chatterset
        self._me = me
        chatterset.userRemoved.connect(self._checkUserQuit)

        self.last_timestamp = None

        # Query flasher
        self.blinker = QtCore.QTimer()
        self.blinker.timeout.connect(self.blink)
        self.blinked = False

        # Table width of each chatter's name cell...
        self.maxChatterWidth = 100  # TODO: This might / should auto-adapt

        # Perform special setup for public channels as opposed to private ones
        self.name = name
        self.private = private

        self.sortCall = ScheduledCall(self._sortChatters)

        if not self.private:
            # Properly and snugly snap all the columns
            self.nickList.horizontalHeader().setSectionResizeMode(Chatter.RANK_COLUMN, QtWidgets.QHeaderView.Fixed)
            self.nickList.horizontalHeader().resizeSection(Chatter.RANK_COLUMN, Formatters.NICKLIST_COLUMNS['RANK'])

            self.nickList.horizontalHeader().setSectionResizeMode(Chatter.AVATAR_COLUMN, QtWidgets.QHeaderView.Fixed)
            self.nickList.horizontalHeader().resizeSection(Chatter.AVATAR_COLUMN, Formatters.NICKLIST_COLUMNS['AVATAR'])

            self.nickList.horizontalHeader().setSectionResizeMode(Chatter.STATUS_COLUMN, QtWidgets.QHeaderView.Fixed)
            self.nickList.horizontalHeader().resizeSection(Chatter.STATUS_COLUMN, Formatters.NICKLIST_COLUMNS['STATUS'])

            self.nickList.horizontalHeader().setSectionResizeMode(Chatter.SORT_COLUMN, QtWidgets.QHeaderView.Stretch)

            self.nickList.itemDoubleClicked.connect(self.nickDoubleClicked)
            self.nickList.itemPressed.connect(self.nickPressed)

            self.nickFilter.textChanged.connect(self.filterNicks)

        else:
            self.nickFrame.hide()
            self.announceLine.hide()

        self.chatEdit.returnPressed.connect(self.sendLine)
        self.chatEdit.setChatters(self.chatters)

    def _sortChatters(self):
        self.nickList.sortItems(Chatter.SORT_COLUMN)

    def joinChannel(self, index):
        """ join another channel """
        channel = self.channelsComboBox.itemText(index)
        if channel.startswith('#'):
            self.chat_widget.autoJoin([channel])

    def keyReleaseEvent(self, keyevent):
        """
        Allow the ctrl-C event.
        """
        if keyevent.key() == 67:
            self.chat_log.copy()

    def resizeEvent(self, size):
        BaseClass.resizeEvent(self, size)
        self.chat_log.setTextWidth()

    def showEvent(self, event):
        self.stopBlink()
        self.chat_log.setTextWidth()
        return BaseClass.showEvent(self, event)

    def clear(self):
        self.chat_log.clear()
        self.last_timestamp = 0

    @QtCore.pyqtSlot()
    def filterNicks(self):
        for chatter in self.chatters.values():
            chatter.setVisible(chatter.isFiltered(self.nickFilter.text().lower()))

    def updateUserCount(self):
        count = len(self.chatters)
        self.nickFilter.setPlaceholderText(str(count) + " users... (type to filter)")

        if self.nickFilter.text():
            self.filterNicks()

    @QtCore.pyqtSlot()
    def blink(self):
        if self.blinked:
            self.blinked = False
            self.chat_widget.tabBar().setTabText(self.chat_widget.indexOf(self), self.name)
        else:
            self.blinked = True
            self.chat_widget.tabBar().setTabText(self.chat_widget.indexOf(self), "")

    @QtCore.pyqtSlot()
    def stopBlink(self):
        self.blinker.stop()
        self.chat_widget.tabBar().setTabText(self.chat_widget.indexOf(self), self.name)

    @QtCore.pyqtSlot()
    def startBlink(self):
        self.blinker.start(QUERY_BLINK_SPEED)

    @QtCore.pyqtSlot()
    def pingWindow(self):
        QtWidgets.QApplication.alert(self.chat_widget.client)

        if not self.isVisible() or QtWidgets.QApplication.activeWindow() != self.chat_widget.client:
            if self.oneMinuteOrOlder():
                if self.chat_widget.client.soundeffects:
                    util.THEME.sound("chat/sfx/query.wav")

        if not self.isVisible():
            if not self.blinker.isActive() and not self == self.chat_widget.currentWidget():
                self.startBlink()

    def printAnnouncement(self, text, color, size, scroll_forced=True):
        text = util.irc_escape(text, self.chat_widget.a_style)
        formatter = Formatters.FORMATTER_ANNOUNCEMENT
        line = formatter.format(size=size, color=color, text=text)
        self.chat_log.addLine(line)
        if scroll_forced:
            self.chat_log.scrollToBottom()

    def printLine(self, chname, text, scroll_forced=False,
                  formatter=Formatters.FORMATTER_MESSAGE):
        chatter = self._chatterset.get(chname)
        if chatter is not None and chatter.player is not None:
            player = chatter.player
        else:
            player = IRCPlayer(chname)

        displayName = chname
        if player.clan is not None:
            displayName = "<b>[%s]</b>%s" % (player.clan, chname)

        # Play a ping sound and flash the title under certain circumstances
        mentioned = text.find(self.chat_widget.client.creds.login) != -1
        if mentioned or (self.private and not (formatter is Formatters.FORMATTER_RAW and text == "quit.")):
            self.pingWindow()

        avatar = None
        if chatter is not None and chatter in self.chatters:
            chatwidget = self.chatters[chatter]
            color = chatwidget.foreground().color().name()
            avatarTip = chatwidget.avatarTip or ""
            if chatter.player is not None:
                avatar = chatter.player.avatar
                if avatar is not None:
                    avatar = avatar["url"]
        else:
            # Fallback and ask the client. We have no Idea who this is.
            color = self.chat_widget.client.player_colors.getUserColor(player.id)

        if mentioned:
            color = self.chat_widget.client.player_colors.getColor("you")

        text = util.irc_escape(text, self.chat_widget.a_style)

        avatar_img = None
        if avatar is not None:
            pix = util.respix(avatar)
            if pix:
                self.chat_log.addAvatar(avatar, pix)
                avatar_img = avatar

        line = Formatters.format(formatter, avatar=avatar,
                                 time=self.timestamp(), avatarTip=avatarTip,
                                 name=displayName, color=color,
                                 width=self.maxChatterWidth, text=text)
        self.chat_log.addLine(line)

        if scroll_forced:
            self.chat_log.scrollToBottom()

    def _chname_has_avatar(self, chname):
        if chname not in self._chatterset:
            return False
        chatter = self._chatterset[chname]

        if chatter.player is None:
            return False
        if chatter.player.avatar is None:
            return False
        return True

    def printMsg(self, chname, text, scroll_forced=False):
        self.printLine(chname, text, scroll_forced,
                       Formatters.FORMATTER_MESSAGE)

    def printAction(self, chname, text, scroll_forced=False, server_action=False):
        if server_action:
            fmt = Formatters.FORMATTER_RAW
        else:
            fmt = Formatters.FORMATTER_ACTION
        self.printLine(chname, text, scroll_forced, fmt)

    def printRaw(self, chname, text, scroll_forced=False):
        """
        Print an raw message in the chat log of the channel
        """
        chatter = self._chatterset.get(chname)
        try:
            _id = chatter.player.id
        except AttributeError:
            _id = -1

        color = self.chat_widget.client.player_colors.getUserColor(_id)

        # Play a ping sound
        if self.private and chname != self.chat_widget.client.creds.login:
            self.pingWindow()

        formatter = Formatters.FORMATTER_RAW
        line = formatter.format(time=self.timestamp(), name=chname,
                                color=color, width=self.maxChatterWidth,
                                text=text)
        self.chat_log.addLine(line)

        if scroll_forced:
            self.chat_log.scrollToBottom()

    def timestamp(self):
        """ returns a fresh timestamp string once every minute, and an empty string otherwise """
        timestamp = time.strftime("%H:%M")
        if self.last_timestamp != timestamp:
            self.last_timestamp = timestamp
            return timestamp
        else:
            return ""

    def oneMinuteOrOlder(self):
        timestamp = time.strftime("%H:%M")
        return self.last_timestamp != timestamp

    @QtCore.pyqtSlot(QtWidgets.QTableWidgetItem)
    def nickDoubleClicked(self, item):
        chatter = self.nickList.item(item.row(), Chatter.SORT_COLUMN)  # Look up the associated chatter object
        chatter.doubleClicked(item)

    @QtCore.pyqtSlot(QtWidgets.QTableWidgetItem)
    def nickPressed(self, item):
        if QtWidgets.QApplication.mouseButtons() == QtCore.Qt.RightButton:
            # Look up the associated chatter object
            chatter = self.nickList.item(item.row(), Chatter.SORT_COLUMN)
            chatter.contextMenu(self.nickList)

    def addChatter(self, chatter, join=False):
        """
        Adds an user to this chat channel, and assigns an appropriate icon depending on friendship and FAF player status
        """
        if chatter not in self.chatters:
            item = Chatter(chatter, self,
                           self.chat_widget, self._me)
            self.chatters[chatter] = item
            self._insertChatter(item)

        self.chatters[chatter].update()

        self.updateUserCount()

        if join and self.chat_widget.client.joinsparts:
            self.printAction(chatter.name, "joined the channel.", server_action=True)

    def _insertChatter(self, chatter):
        row = self.nickList.rowCount()
        self.nickList.insertRow(row)
        self.nickList.setItem(row, Chatter.SORT_COLUMN, chatter)
        row = chatter.row()
        self.nickList.setItem(row, Chatter.RANK_COLUMN, chatter.rankItem)
        self.nickList.setItem(row, Chatter.AVATAR_COLUMN, chatter.avatarItem)
        self.nickList.setItem(row, Chatter.STATUS_COLUMN, chatter.statusItem)

    def removeChatter(self, chatter, server_action=None):
        if chatter in self.chatters:
            self.nickList.removeRow(self.chatters[chatter].row())
            del self.chatters[chatter]

            if server_action and (self.chat_widget.client.joinsparts or self.private):
                self.printAction(chatter.name, server_action, server_action=True)
                self.stopBlink()

        self.updateUserCount()

    def verifySortOrder(self, chatter):
        row = chatter.row()
        next_chatter = self.nickList.item(row + 1, Chatter.SORT_COLUMN)
        prev_chatter = self.nickList.item(row - 1, Chatter.SORT_COLUMN)

        if (next_chatter is not None and chatter > next_chatter or
           prev_chatter is not None and chatter < prev_chatter):
            self.sortCall.scheduleCall()

    def setAnnounceText(self, text):
        self.announceLine.clear()
        self.announceLine.setText("<style>a{color:cornflowerblue}</style><b><font color=white>" + util.irc_escape(text) + "</font></b>")

    @QtCore.pyqtSlot()
    def sendLine(self, target=None):
        self.stopBlink()

        if not target:
            target = self.name  # pubmsg in channel

        line = self.chatEdit.text()
        # Split into lines if newlines are present
        fragments = line.split("\n")
        for text in fragments:
            # Compound wacky Whitespace
            text = re.sub('\s', ' ', text)
            text = text.strip()

            # Reject empty messages
            if not text:
                continue

            # System commands
            if text.startswith("/"):
                if text.startswith("/join "):
                    self.chat_widget.join(text[6:])
                elif text.startswith("/topic "):
                    self.chat_widget.setTopic(self.name, text[7:])
                elif text.startswith("/msg "):
                    blobs = text.split(" ")
                    self.chat_widget.sendMsg(blobs[1], " ".join(blobs[2:]))
                elif text.startswith("/me "):
                    if self.chat_widget.sendAction(target, text[4:]):
                        self.printAction(self.chat_widget.client.creds.login, text[4:], True)
                    else:
                        self.printAction("IRC", "action not supported", True)
                elif text.startswith("/seen "):
                    if self.chat_widget.sendMsg("nickserv", "info %s" % (text[6:])):
                        self.printAction("IRC", "info requested on %s" % (text[6:]), True)
                    else:
                        self.printAction("IRC", "not connected", True)
            else:
                if self.chat_widget.sendMsg(target, text):
                    self.printMsg(self.chat_widget.client.creds.login, text, True)
        self.chatEdit.clear()

    def _checkUserQuit(self, chatter):
        self.removeChatter(chatter)
