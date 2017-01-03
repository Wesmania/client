from . import version
import os
import sys
import trueskill
import fafpath
from PyQt4 import QtCore

if sys.platform == 'win32':
    import win32api
    import win32con
    import win32security
    from . import admin

trueskill.setup(mu=1500, sigma=500, beta=250, tau=5, draw_probability=0.10)

_settings = QtCore.QSettings(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, "ForgedAllianceForever", "FA Lobby")
_unpersisted_settings = {}

VERSION = version.get_release_version(fafpath.get_resdir())

def is_development_version():
    return version.is_development_version(VERSION)


# FIXME: Don't initialize proxy code that shows a dialogue box on import
no_dialogs = False

def is_beta():
    return environment == 'development'

if _settings.contains('client/force_environment'):
    environment = _settings.value('client/force_environment', 'development')
else:
    environment = 'production'

defaults = os.path.join(fafpath.get_resdir(), "default_settings", environment + ".ini")
defaults = QtCore.QSettings(defaults, QtCore.QSettings.IniFormat)

class Settings:
    """
    This wraps QSettings, fetching default values from the
    selected configuration module if the key isn't found.
    """

    @staticmethod
    def get(key, default=None, type=str):
        # Get from a local dict cache before hitting QSettings
        # this is for properties such as user.login which we
        # don't necessarily want to persist
        if key in _unpersisted_settings:
            return _unpersisted_settings[key]
        # Hit QSettings to see if the user has defined a value for the key
        if _settings.contains(key):
            return _settings.value(key, type=type)
        # Try out our defaults for the current environment
        if defaults.contains(key):
            return defaults.value(key, type=type)
        return default

    @staticmethod
    def set(key, value, persist=True):
        _unpersisted_settings[key] = value
        if not persist:
            _settings.remove(key)
        else:
            _settings.setValue(key, value)

    @staticmethod
    def remove(key):
        if key in _unpersisted_settings:
            del _unpersisted_settings[key]
        if _settings.contains(key):
            _settings.remove(key)

    @staticmethod
    def contains(key):
        return (key in _unpersisted_settings or
                _settings.contains(key) or
                defaults.contains(key))
