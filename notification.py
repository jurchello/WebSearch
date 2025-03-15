import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject, Pango

class Notification(Gtk.Window):
    def __init__(self, message):
        super().__init__()

        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_name("TransparentWindow")
        self.apply_css()

        self.set_decorated(False)
        self.set_accept_focus(False)
        self.set_size_request(200, -1)
        self.set_keep_above(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        label = Gtk.Label(label=message)
        label.set_line_wrap(True)
        label.set_max_width_chars(10)
        label.set_ellipsize(Pango.EllipsizeMode.NONE)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        box.pack_start(label, True, True, 0)
        self.add(box)

        self.show_all()

        width, height = self.get_size()
        self.set_size_request(100, height)
        monitor = screen.get_monitor_geometry(0)
        screen_width = monitor.width
        width, height = self.get_size()
        x = screen_width - width - 10
        y = 10
        self.move(x, y)

        GObject.timeout_add(2000, self.close_window)

    def close_window(self):
        self.destroy()
        return False

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            #TransparentWindow {
                background-color: rgba(0, 0, 0, 0.7);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()
        context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
