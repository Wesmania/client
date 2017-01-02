from Setting import Setting, PrefixedPathSetting
import fafpath

_userdir = fafpath.get_userdir()

ignore_admin = Setting("client/ignore_admin", bool)
force_environment = Setting("client/force_environment")
auto_bugreport = Setting("client/auto_bugreport", bool)

data_path = PrefixedPathSetting("client/data_path", _userdir)
logs_path = PrefixedPathSetting("client/logs/path", _userdir)
logs_level = PrefixedPathSetting("client/logs/level", _userdir)
logs_max_size = PrefixedPathSetting("client/logs/max_size", _userdir)
logs_buffer_size = PrefixedPathSetting("client/logs/buffer_size", _userdir)

host = Setting("host")
