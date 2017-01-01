import os
import util
from common import cui
from PyQt4.QtGui import QWidget, QPushButton, QLineEdit, QFileDialog
from PyQt4.QtCore import pyqtSignal, pyqtSlot
_FormClass, _BaseClass = util.loadUiType(cui('PathSelect.ui'))

class PathSelectWidget(_FormClass, _BaseClass):
    """
    A widget class that allows for path browsing and selection.
    """

    newPath = pyqtSignal(str)
    """
    Signal emitted when a new path is set.
    """

    def __init__(self, *args, **kwargs):
        _BaseClass.__init__(self, *args, **kwargs)
        self.setupUi(self)

        self._buttonLabel = self.property('buttonLabel')
        """Label on the 'browse path' button."""

        self._selectedPath = self.property('selectedPath')
        """Selected path."""

        self.defaultDialogPath = self.property('defaultDialogPath')
        """Default path shown by the path browsing window."""

        self.fileDialogLabel = self.property('fileDialogLabel')
        """Path browsing window label."""

        self._browseButton = self.findChild(QPushButton, 'browseButton')
        self._pathLabel = self.findChild(QLineEdit, 'pathLabel')

        self._browseButton.clicked.connect(self._launchBrowseWindow)
        self._updateUI()

    @property
    def buttonLabel(self):
        return self._buttonLabel

    @buttonLabel.setter
    def buttonLabel(self, value):
        self._buttonLabel = value
        self._updateUI()

    @property
    def selectedPath(self):
        return self._selectedPath

    @selectedPath.setter
    def selectedPath(self, value):
        self._selectedPath = value
        self._updateUI()

    def _updateUI(self):
        self._pathLabel.setText(
                self._selectedPath if not self._selectedPath.isNull() else '')
        self._browseButton.setText(
                self._buttonLabel if not self._buttonLabel.isNull() else '')

    @pyqtSlot(bool)
    def _launchBrowseWindow(self):
        path = QFileDialog.getExistingDirectory(self,
                self.fileDialogLabel,
                self.defaultDialogPath,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if not path.isNull():
            self.selectedPath = path
            self._updateUI()
            self.newPath.emit(str(self.selectedPath))
