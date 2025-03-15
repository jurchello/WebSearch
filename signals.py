import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject

class WebSearchSignalEmitter(GObject.GObject):
    __gsignals__ = {
        "sites-fetched": (GObject.SignalFlags.RUN_FIRST, None, (object,))
    }

    def __init__(self):
        GObject.GObject.__init__(self)
