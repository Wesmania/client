class qtProperty(object):
    """
    Class for conveniently wrapping Qt widget properties. Since this is
    a descriptor, it should be defined at the *class* level, not at the
    *instance* level in __init__.
    """
    def __init__(self, name):
        self._name = name

    def __get__(self, obj, cls = None):
        if obj is None:
            raise AttributeError
        return obj.property(self._name)

    def __set__(self, obj, val):
        if obj is None:
            return
        obj.setProperty(self._name, val)
