import os
import sys
from config import modules as cfg

if sys.platform == 'win32':
    import win32api
    import win32con
    import win32security
    from config import admin

def set_data_path_permissions():
    """
    Set the owner of C:\ProgramData\FAForever recursively to the current user
    """
    if sys.platform != 'win32':
        return

    if not admin.isUserAdmin():
        win32api.MessageBox(0, "FA Forever needs to fix folder permissions due to user change. Please confirm the following two admin prompts.", "User changed")
    if sys.platform == 'win32' and (not 'CI' in os.environ):
        data_path = cfg.client.data_path.get()
        if os.path.exists(data_path):
            my_user = win32api.GetUserNameEx(win32con.NameSamCompatible)
            admin.runAsAdmin(["icacls", data_path, "/setowner", my_user, "/T"])
            admin.runAsAdmin(["icacls", data_path, "/reset", "/T"])

def check_data_path_permissions():
    """
    Checks if the current user is owner of C:\ProgramData\FAForever
    Fixes the permissions in case that FAF was run as different user before
    """
    if sys.platform == 'win32' and (not 'CI' in os.environ):
        data_path = cfg.client.data_path.get()
        if os.path.exists(data_path):
            my_user = win32api.GetUserNameEx(win32con.NameSamCompatible)
            sd = win32security.GetFileSecurity(data_path, win32security.OWNER_SECURITY_INFORMATION)
            owner_sid = sd.GetSecurityDescriptorOwner()
            name, domain, type = win32security.LookupAccountSid(None, owner_sid)
            data_path_owner = "%s\\%s" % (domain, name)

            if (my_user != data_path_owner):
                set_data_path_permissions()

def make_dirs():
    check_data_path_permissions()
    for dir in [
        cfg.client.data_path.get(),
        cfg.client.logs_path.get(),
        cfg.client.bin_path.get(),
        cfg.client.mods_path.get(),
        cfg.client.engine_path.get(),
        cfg.client.maps_path.get(),
    ]:
        if dir is None:
            raise Exception("Missing configured path for {}".format(dir))
        if not os.path.isdir(dir):
            try:
                os.makedirs(dir)
            except IOError, e:
                set_data_path_permissions()
                os.makedirs(path)
