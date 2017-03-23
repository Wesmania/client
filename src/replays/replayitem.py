import os
import time

import util
from PyQt5 import QtCore, QtWidgets, QtGui

from config import Settings
from fa import maps
from games.moditem import mods


class ReplayItemDelegate(QtWidgets.QStyledItemDelegate):
    
    def __init__(self, *args, **kwargs):
        QtWidgets.QStyledItemDelegate.__init__(self, *args, **kwargs)
        
    def paint(self, painter, option, index, *args, **kwargs):
        self.initStyleOption(option, index)
                
        painter.save()
        
        html = QtGui.QTextDocument()
        html.setHtml(option.text)
        
        icon = QtGui.QIcon(option.icon)
        iconsize = icon.actualSize(option.rect.size())
        
        # clear icon and text before letting the control draw itself because we're rendering these parts ourselves
        option.icon = QtGui.QIcon()
        option.text = ""  
        option.widget.style().drawControl(QtWidgets.QStyle.CE_ItemViewItem, option, painter, option.widget)
        
        # Shadow
        # painter.fillRect(option.rect.left()+8-1, option.rect.top()+8-1, iconsize.width(), iconsize.height(), QtGui.QColor("#202020"))

        # Icon
        icon.paint(painter, option.rect.adjusted(5-2, -2, 0, 0), QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        
        # Frame around the icon
#        pen = QtWidgets.QPen()
#        pen.setWidth(1)
#        pen.setBrush(QtGui.QColor("#303030"))  #FIXME: This needs to come from theme.
#        pen.setCapStyle(QtCore.Qt.RoundCap)
#        painter.setPen(pen)
#        painter.drawRect(option.rect.left()+5-2, option.rect.top()+5-2, iconsize.width(), iconsize.height())

        # Description
        painter.translate(option.rect.left() + iconsize.width() + 10, option.rect.top() + 10)
        clip = QtCore.QRectF(0, 0, option.rect.width()-iconsize.width() - 10 - 5, option.rect.height())
        html.drawContents(painter, clip)
  
        painter.restore()
        

    def sizeHint(self, option, index, *args, **kwargs):
        clip = index.model().data(index, QtCore.Qt.UserRole)
        self.initStyleOption(option, index)
        html = QtGui.QTextDocument()
        html.setHtml(option.text)
        html.setTextWidth(240)
        if clip:
            return QtCore.QSize(215, clip.height)
        else:
            return QtCore.QSize(215, 35)


class Replay():
    REPLAY_URL = "{}/faf/vault/replay_vault/replay.php?id={}"
    STILL_PLAYING_TIME = 4294967295

    def __init__(self, uid):
        self.uid            = uid
        self.name           = None
        self.mapname        = None
        self.mod            = None

        self.startTime      = None
        self.endTime        = None
        self.duration       = None

        self.teams          = {}
        self.players        = []

    def update(self, message):
        self.name      = message["name"]
        self.mapname   = message["map"]
        self.mod       = message["mod"]

        self.startTime = message['start']
        self.endTime   = message['end'] if message['end'] != self.STILL_PLAYING_TIME else None
        self.duration  = message["duration"]

    def setPlayers(self, players):
        self.players = players
        self.setPlayerTeams()

    def setPlayerTeams(self):
        if self.mod == "phantomx" or self.mod == "murderparty":
            self.teams = {1: list(self.players)}
            return

        for player in self.players:  # player -> teams & playerscore -> teamscore
            team = int(player["team"])
            teamlist = self.teams.setdefault(team, [])
            teamlist.append(player)

        if len(self.players) == len(self.teams):  # some kind of FFA
            self.teams = {1: list(self.players)}

    def isFFA(self):
        return len(self.teams) == 1

    def getMVP(self):
        score = lambda p: int(p["score"]) if "score" in p else None
        scores = [(player, score(player)) for player in self.players]
        return max(scores, key = lambda t: t[1])[0]

    def getMVT(self):
        score = lambda p: int(p["score"]) if "score" in p else 0
        scores = [(team, sum(score(player) for player in self.teams[team])) for team in self.teams]
        return max(scores, key = lambda t: t[1])[0]

    def getFaction(self, player):
        FAF_factions = {
            1: "UEF",
            2: "Aeon",
            3: "Cybran",
            4: "Seraphim",
            5: "Random",
        }
        Nomad_factions = {
            1: "UEF",
            2: "Aeon",
            3: "Cybran",
            4: "Seraphim",
            5: "Nomads",
            6: "Random",
        }

        if self.mod == "nomads":
            factions = Nomad_factions
        else:
            factions = FAF_factions

        if "faction" not in player:
            return "Missing"

        return factions.get(player["faction"], "Broken")

    def getBiggestTeamSize(self):
        return max([len(team) for team in self.teams.values()] + [0])

    def getUrl(self, host):
        return self.REPLAY_URL.format(host, self.uid)

    @property
    def modString(self):
        if self.mod in mods:
            return mods[self.mod].name
        return self.mod

    @property
    def mapString(self):
        return maps.getDisplayName(self.mapname)


class ReplayItem(QtWidgets.QTreeWidgetItem):
    # list element
    FORMATTER_REPLAY                = str(util.readfile("replays/formatters/replay.qthtml"))
    # replay-info elements
    FORMATTER_REPLAY_INFORMATION    = "<h2 align='center'>Replay UID : {uid}</h2><table border='0' cellpadding='0' cellspacing='5' align='center'><tbody>{teams}</tbody></table>"
    FORMATTER_REPLAY_TEAM_SPOILED   = "<tr><td colspan='3' align='center' valign='middle'><font size='+2'>{title}</font></td></tr>{players}"
    FORMATTER_REPLAY_FFA_SPOILED    = "<tr><td colspan='3' align='center' valign='middle'><font size='+2'>Win</font></td></tr>{winner}<tr><td colspan=3 align='center' valign='middle'><font size='+2'>Lose</font></td></tr>{players}"
    FORMATTER_REPLAY_TEAM2_SPOILED = "<td><table border=0><tr><td colspan='3' align='center' valign='middle'><font size='+2'>{title}</font></td></tr>{players}</table></td>"
    FORMATTER_REPLAY_TEAM2         = "<td><table border=0>{players}</table></td>"
    FORMATTER_REPLAY_PLAYER_SCORE   = "<td align='center' valign='middle' width='20'>{player_score}</td>"
    FORMATTER_REPLAY_PLAYER_ICON    = "<td width='40'><img src='{faction_icon_uri}' width='40' height='20'></td>"
    FORMATTER_REPLAY_PLAYER_LABEL   = "<td align='{alignment}' valign='middle' width='130'>{player_name} ({player_rating})</td>"

    def __init__(self, uid, parent, *args, **kwargs):
        QtWidgets.QTreeWidgetItem.__init__(self, *args, **kwargs)

        self.replay         = Replay(uid)
        self.parent         = parent
        self.height         = 70
        self.viewtext       = None
        self.viewtextPlayer = None
        self.client         = None
        self.title          = None
        self.host           = None
        self.duration       = None

        self.live_delay     = False

        self.moreInfo       = False
        self.replayInfo     = False
        self.spoiled        = False

        self.access         = None

        self.options        = []

        self.setHidden(True)
        self.extraInfoWidth  = 0  # panel with more information
        self.extraInfoHeight = 0  # panel with more information

    def update(self, message, client):
        """ Updates this item from the message dictionary supplied """

        self.client = client
        self.replay.update(message)

        if self.replay.endTime is None:
            seconds = time.time() - self.replay.startTime
            if seconds > 86400:  # more than 24 hours
                self.duration = "<font color='darkgrey'>end time<br />&nbsp;missing</font>"
            elif seconds > 7200:  # more than 2 hours
                self.duration = time.strftime('%H:%M:%S', time.gmtime(seconds)) + "<br />?playing?"
            elif seconds < 300:  # less than 5 minutes
                self.duration = time.strftime('%H:%M:%S', time.gmtime(seconds)) + "<br />&nbsp;<font color='darkred'>playing</font>"
                self.live_delay = True
            else:
                self.duration = time.strftime('%H:%M:%S', time.gmtime(seconds)) + "<br />&nbsp;playing"
        else:
            self.duration = time.strftime('%H:%M:%S', time.gmtime(self.replay.duration))

        self.startDate = time.strftime("%Y-%m-%d", time.localtime(self.replay.endTime))
        startHour = time.strftime("%H:%M", time.localtime(self.replay.startTime))

        self.icon = maps.preview(self.replay.mapname)
        if not self.icon:
            self.client.downloader.downloadMap(self.replay.mapname, self, True)
            self.icon = util.icon("games/unknown_map.png")

#        self.title      = message['title']
#        self.teams      = message['teams']
#        self.access     = message.get('access', 'public')
#        self.mod        = message['featured_mod']
#        self.host       = message["host"]
#        self.options    = message.get('options', [])
#        self.numplayers = message.get('num_players', 0)
#        self.slots      = message.get('max_players',12)

        self.viewtext = self.FORMATTER_REPLAY.format(time=startHour, name=self.replay.name, map=self.replay.mapString,
                                                     duration=self.duration, mod=self.replay.modString)

    def infoPlayers(self, players):
        """ processes information from the server about a replay into readable extra information for the user,
                also calls method to show the information """
        self.replay.setPlayers(players)
        self.moreInfo = True
        self.generateInfoPlayersHtml()

    def is2TeamGame(self):
        return len(self.replay.teams) == 2

    def generateInfoPlayersHtml(self):
        """  Creates the ui and extra information about a replay,
             Either teamWin or winner must be set if the replay is to be spoiled """

        teams = ""
        winnerHTML = ""

        self.spoiled = not self.parent.spoilerCheckbox.isChecked()
        mvp = self.replay.getMVP()
        mvt = self.replay.getMVT()

        for i, team in enumerate(t for t in self.replay.teams if t != -1):

            players = ""
            for player in self.replay.teams[team]:
                alignment, playerIcon, playerLabel, playerScore = self.generatePlayerHTML(i, player)

                if self.replay.isFFA() and player["score"] == mvp["score"] and self.spoiled:
                    winnerHTML += "<tr>%s%s%s</tr>" % (playerScore, playerIcon, playerLabel)
                elif alignment == "left":
                    players += "<tr>%s%s%s</tr>" % (playerScore, playerIcon, playerLabel)
                else:  # alignment == "right"
                    players += "<tr>%s%s%s</tr>" % (playerLabel, playerIcon, playerScore)

            if self.spoiled:
                if self.replay.isFFA():  # FFA in rows: Win ... Lose ....
                    teams += self.FORMATTER_REPLAY_FFA_SPOILED.format(winner=winnerHTML, players=players)
                else:
                    if "playing" in self.duration:  # FIXME - horribly fragile
                        teamTitle = "Playing"
                    elif team == mvt:
                        teamTitle = "Win"
                    else:
                        teamTitle = "Lose"

                    if self.is2TeamGame():  # pack team in <table>
                        teams += self.FORMATTER_REPLAY_TEAM2_SPOILED.format(title=teamTitle, players=players)
                    else:  # just row on
                        teams += self.FORMATTER_REPLAY_TEAM_SPOILED.format(title=teamTitle, players=players)
            else:
                if self.is2TeamGame():  # pack team in <table>
                    teams += self.FORMATTER_REPLAY_TEAM2.format(players=players)
                else:  # just row on
                    teams += players

            if self.is2TeamGame() and i == 0:  # add the 'vs'
                teams += "<td align='center' valign='middle' height='100%'><font color='black' size='+4'>VS</font></td>"

        if self.is2TeamGame():  # prepare the package to 'fit in' with its <td>s
            teams = "<tr>%s</tr>" % teams

        self.replayInfo = self.FORMATTER_REPLAY_INFORMATION.format(uid=self.replay.uid, teams=teams)

        if self.isSelected():
            self.parent.replayInfos.clear()
            self.resize()
            self.parent.replayInfos.setHtml(self.replayInfo)

    def generatePlayerHTML(self, i, player):
        if i == 1 and self.is2TeamGame():
            alignment = "right"
        else:
            alignment = "left"

        playerLabel = self.FORMATTER_REPLAY_PLAYER_LABEL.format(player_name=player["name"],
                                                                player_rating=player["rating"], alignment=alignment)

        iconUrl = os.path.join(util.COMMON_DIR, "replays/%s.png" % self.replay.getFaction(player))

        playerIcon = self.FORMATTER_REPLAY_PLAYER_ICON.format(faction_icon_uri=iconUrl)

        if self.spoiled and not self.replay.mod == "ladder1v1":
            playerScore = self.FORMATTER_REPLAY_PLAYER_SCORE.format(player_score=player["score"])
        else:  # no score for ladder
            playerScore = self.FORMATTER_REPLAY_PLAYER_SCORE.format(player_score=" ")

        return alignment, playerIcon, playerLabel, playerScore

    def resize(self):
        if self.isSelected():
            if self.extraInfoWidth == 0 or self.extraInfoHeight == 0:
                if len(self.replay.teams) == 1:  # ladder, FFA
                    self.extraInfoWidth = 275
                    self.extraInfoHeight = 75 + (len(self.replay.players) + 1) * 25  # + 1 -> second title
                elif self.is2TeamGame():  # Team vs Team
                    self.extraInfoWidth = 500
                    self.extraInfoHeight = 75 + self.replay.getBiggestTeamSize() * 22
                else:  # FAF
                    self.extraInfoWidth = 275
                    self.extraInfoHeight = 75 + (len(self.replay.players) + len(self.replay.teams)) * 25

            self.parent.replayInfos.setMinimumWidth(self.extraInfoWidth)
            self.parent.replayInfos.setMaximumWidth(600)

            self.parent.replayInfos.setMinimumHeight(self.extraInfoHeight)
            self.parent.replayInfos.setMaximumHeight(self.extraInfoHeight)

    def pressed(self, item):
        menu = QtWidgets.QMenu(self.parent)
        actionDownload = QtWidgets.QAction("Download replay", menu)
        actionDownload.triggered.connect(self.downloadReplay)
        menu.addAction(actionDownload)
        menu.popup(QtGui.QCursor.pos())

    def downloadReplay(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.replay.getUrl(Settings.get('content/host'))))

    def display(self, column):
        if column == 0:
            return self.viewtext
        if column == 1:
            return self.viewtext

    def data(self, column, role):
        if role == QtCore.Qt.DisplayRole:
            return self.display(column)
        elif role == QtCore.Qt.UserRole:
            return self
        return super(ReplayItem, self).data(column, role)

    def permutations(self, items):
        """  Yields all permutations of the items. """
        if items is []:
            yield []
        else:
            for i in range(len(items)):
                for j in self.permutations(items[:i] + items[i+1:]):
                    yield [items[i]] + j

    def __ge__(self, other):
        """  Comparison operator used for item list sorting """
        return not self.__lt__(other)

    def __lt__(self, other):
        """ Comparison operator used for item list sorting """
        if not self.client: return True  # If not initialized...
        if not other.client: return False
        # Default: uid
        return self.replay.uid < other.replay.uid
