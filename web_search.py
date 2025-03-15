#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# ----------------------------------------------------------------------------
"""
    WebSearch - a Gramplet for searching genealogical websites
    Allows searching for genealogical resources based on the active person's, place's, or source's data.
    Integrates multiple regional websites into a single sidebar tool with customizable URL templates.
"""
# Standard Python libraries
import os
import csv
import sys
import re
import json
import traceback
import threading
import webbrowser
from enum import Enum

# Own project imports
from constants import *
from qr_window import QRCodeWindow
from site_finder import SiteFinder
from config_ini_manager import ConfigINIManager
from settings_ui_manager import SettingsUIManager
from website_loader import WebsiteLoader
from notification import Notification
from signals import WebSearchSignalEmitter
from url_formatter import UrlFormatter

# GTK
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, Pango

# GRAMPS API
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.display import display_url
from gramps.gen.config import config as configman
from gramps.gen.plug.menu import BooleanListOption, EnumeratedListOption, StringOption
from gramps.gen.lib import Note, Attribute
from gramps.gen.db import DbTxn

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

class WebSearch(Gramplet):
    __gsignals__ = {
        "sites-fetched": (GObject.SignalFlags.RUN_FIRST, None, (object,))
    }

    def __init__(self, gui):
        self.signal_emitter = WebSearchSignalEmitter()
        self.config_ini_manager = ConfigINIManager()
        self.settings_ui_manager = SettingsUIManager(self.config_ini_manager)
        self.website_loader = WebsiteLoader()
        self.url_formatter = UrlFormatter(self.config_ini_manager)
        Gramplet.__init__(self, gui)

    def init(self):
        self.gui.WIDGET = self.build_gui()
        container = self.gui.get_container_widget()
        if self.gui.textview in container.get_children():
            container.remove(self.gui.textview)
        container.add(self.gui.WIDGET)
        self.gui.WIDGET.show_all()
        self.populate_links({}, SupportedNavTypes.PEOPLE.value)

    def post_init(self):
        self.signal_emitter.connect("sites-fetched", self.on_sites_fetched)
        locales, domains, include_global = self.website_loader.get_domains_data(self.config_ini_manager)
        if not self.__use_openai:
            return
        if not self.__openai_api_key:
            print("⚠️ ERROR: No OpenAI API Key found.", file=sys.stderr)
            return
        self.finder = SiteFinder(self.__openai_api_key)
        threading.Thread(
            target=self.fetch_sites_in_background,
            args=(domains, locales, include_global),
            daemon=True
        ).start()

    def fetch_sites_in_background(self, csv_domains, locales, include_global):
        print("🔄 Fetching recommended sites in background...")
        skipped_domains = self.website_loader.load_skipped_domains()
        all_excluded_domains = csv_domains.union(skipped_domains)
        try:
            results = self.finder.find_sites(all_excluded_domains, locales, include_global)
            GObject.idle_add(self.signal_emitter.emit, "sites-fetched", results)
        except Exception as e:
            print(f"❌ Error fetching sites: {e}")
            GObject.idle_add(self.signal_emitter.emit, "sites-fetched", None)

    def on_sites_fetched(self, gramplet, results):
        if results:
            try:
                sites = json.loads(results)
                if not isinstance(sites, list):
                    return
                domain_url_pairs = [
                    (site.get("domain", "").strip(), site.get("url", "").strip())
                    for site in sites if site.get("domain") and site.get("url")
                ]
                if domain_url_pairs:
                    self.populate_badges(domain_url_pairs)
            except json.JSONDecodeError as e:
                print(f"❌ JSON Decode Error: {e}")
            except Exception as e:
                print(f"❌ Error processing sites: {e}")

    def db_changed(self):
        self.connect_signal("Person", self.active_person_changed)
        self.connect_signal("Place", self.active_place_changed)
        self.connect_signal("Source", self.active_source_changed)

    def is_true(self, value):
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    def populate_links(self, data, nav_type):
        self.model.clear()
        if len(data) == 0:
            return
        websites = self.website_loader.load_websites(self.config_ini_manager)

        for nav, locale, category, is_enabled, url_pattern, comment in websites:
            if nav == nav_type and self.is_true(is_enabled):
                try:
                    variables = self.url_formatter.check_pattern_variables(url_pattern, data)
                    variables_json = json.dumps(variables)

                    if len(variables["not_found_variables"]):
                        print(f"Locale: {locale}.\n"
                              f"Pattern: {url_pattern}.\n"
                              f"Replaced variables: {variables['replaced_variables']}.\n"
                              f"Not found variables: {variables['not_found_variables']}.\n"
                              f"Empty variables: {variables['empty_variables']}.\n"
                              f"Data: {data}.")
                    final_url = url_pattern % data
                    icon_name = CATEGORY_ICON.get(nav_type, DEFAULT_CATEGORY_ICON)
                    formatted_url = self.url_formatter.format(final_url, variables)

                    hash_value = self.website_loader.generate_hash(final_url)

                    visited_icon = None
                    if self.website_loader.has_hash_in_file(hash_value, VISITED_HASH_FILE_PATH):
                        try:
                            visited_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(ICON_VISITED_PATH, ICON_SIZE, ICON_SIZE)
                        except Exception as e:
                            print(f"❌ Error loading icon: {e}")

                    saved_icon = None
                    if self.website_loader.has_hash_in_file(hash_value, SAVED_HASH_FILE_PATH):
                        try:
                            saved_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(ICON_SAVED_PATH, ICON_SIZE, ICON_SIZE)
                        except Exception as e:
                            print(f"❌ Error loading icon: {e}")

                    self.model.append([icon_name, locale, category, final_url, comment, url_pattern, variables_json, formatted_url, visited_icon, saved_icon])
                except KeyError:
                    print(f"{locale}. Mismatch in template variables: {url_pattern}")
                    pass

    def on_link_clicked(self, tree_view, path, column):
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, 3)
        self.add_icon_event(VISITED_HASH_FILE_PATH, ICON_VISITED_PATH, tree_iter, 8)
        display_url(url)

    def add_icon_event(self, file_path, icon_path, tree_iter, model_icon_pos):
        url = self.model.get_value(tree_iter, 3)
        hash_value = self.website_loader.generate_hash(url)
        if not self.website_loader.has_hash_in_file(hash_value, file_path):
            self.website_loader.save_hash_to_file(hash_value, file_path)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, ICON_SIZE, ICON_SIZE)
                self.model.set_value(tree_iter, model_icon_pos, pixbuf)
            except Exception as e:
                print(f"❌ Error loading icon: {e}")

    def active_person_changed(self, handle):
        person = self.dbstate.db.get_person_from_handle(handle)
        self.person = person
        if not person:
            return

        person_data = self.get_person_data(person)
        self.populate_links(person_data, SupportedNavTypes.PEOPLE.value)
        self.update()

    def active_place_changed(self, handle):
        try:
            place = self.dbstate.db.get_place_from_handle(handle)
            if not place:
                return

            place_data = self.get_place_data(place)
            self.populate_links(place_data, SupportedNavTypes.PLACES.value)
            self.update()
        except Exception as e:
            print(traceback.format_exc())

    def active_source_changed(self, handle):
        source = self.dbstate.db.get_source_from_handle(handle)
        if not source:
            return

        source_data = self.get_source_data(source)
        self.populate_links(source_data, SupportedNavTypes.SOURCES.value)
        self.update()

    def get_person_data(self, person):
        try:
            name = person.get_primary_name().get_first_name().strip()
            middle_name_handling = self.config_ini_manager.get_enum(
                "websearch.middle_name_handling", MiddleNameHandling, DEFAULT_MIDDLE_NAME_HANDLING
            )

            if middle_name_handling == MiddleNameHandling.SEPARATE.value:
                given, middle = (name.split(" ", 1) + [None])[:2] if name else (None, None)
            elif middle_name_handling == MiddleNameHandling.REMOVE.value:
                given, middle = (name.split(" ", 1) + [None])[:2] if name else (None, None)
                middle = None
            elif middle_name_handling == MiddleNameHandling.LEAVE_ALONE.value:
                given, middle = name, None
            else:
                given, middle = name, None

            surname = person.get_primary_name().get_primary().strip() or None
        except Exception as e:
            print(traceback.format_exc())
            given, middle, surname = None, None, None

        birth_year_from, birth_year_to = self.get_birth_years_range(person)
        death_year_from, death_year_to = self.get_death_years_range(person)

        person_data = {
            PersonDataKeys.GIVEN.value: given or "",
            PersonDataKeys.MIDDLE.value: middle or "",
            PersonDataKeys.SURNAME.value: surname or "",
            PersonDataKeys.BIRTH_YEAR.value: self.get_birth_year(person) or "",
            PersonDataKeys.DEATH_YEAR.value: self.get_death_year(person) or "",
            PersonDataKeys.BIRTH_PLACE.value: self.get_birth_place(person) or "",
            PersonDataKeys.BIRTH_ROOT_PLACE.value: self.get_birth_root_place(person) or "",
            PersonDataKeys.DEATH_PLACE.value: self.get_death_place(person) or "",
            PersonDataKeys.DEATH_ROOT_PLACE.value: self.get_death_root_place(person) or "",
            PersonDataKeys.BIRTH_YEAR_FROM.value: birth_year_from or "",
            PersonDataKeys.DEATH_YEAR_FROM.value: death_year_from or "",
            PersonDataKeys.BIRTH_YEAR_TO.value: birth_year_to or "",
            PersonDataKeys.DEATH_YEAR_TO.value: death_year_to or "",
        }
        #print(person_data)

        return person_data

    def get_place_data(self, place):
        try:
            place_name = self.get_place_name(place)
            root_place_name = self.get_root_place_name(place)
        except Exception as e:
            print(traceback.format_exc())
            place_name = None

        place_data = {
            PlaceDataKeys.PLACE.value: place_name or "",
            PlaceDataKeys.ROOT_PLACE.value: root_place_name or "",
        }
        #print(place_data)

        return place_data

    def get_source_data(self, source):
        try:
            title = source.get_title() or None
        except Exception as e:
            print(traceback.format_exc())
            title = None

        source_data = {
            SourceDataKeys.TITLE.value: title or "",
        }
        #print(source_data)

        return source_data

    def get_root_place_name(self, place):
        try:
            if place is None:
                return None
            name = place.get_name()
            if name is None:
                return None
            root_place_name = name.get_value()
            place_ref = place.get_placeref_list()[0] if place.get_placeref_list() else None
            while place_ref:
                p = self.dbstate.db.get_place_from_handle(place_ref.get_reference_handle())
                if p:
                    root_place_name = p.get_name().get_value()
                    place_ref = p.get_placeref_list()[0] if p.get_placeref_list() else None
                else:
                    break
        except Exception as e:
            print(traceback.format_exc())
            return None

        return root_place_name

    def get_birth_year(self, person):
        event = self.get_birth_event(person)
        return self.get_event_exact_year(event)

    def get_birth_years_range(self, person):
        event = self.get_birth_event(person)
        year_from, year_to = self.get_event_years_range(event)
        return year_from, year_to

    def get_death_years_range(self, person):
        event = self.get_death_event(person)
        year_from, year_to = self.get_event_years_range(event)
        return year_from, year_to

    def get_event_years_range(self, event):
        try:
            if not event:
                return None, None
            date = event.get_date_object()
            if date and not date.is_compound():
                exact_year = date.get_year() or None
                return exact_year, exact_year
            if date and date.is_compound():
                start_date = date.get_start_date()
                stop_date = date.get_stop_date()
                year_from = start_date[2] if start_date else None
                year_to = stop_date[2] if stop_date else None
                return year_from, year_to
        except Exception as e:
            print(traceback.format_exc())
        return None, None

    def get_birth_place(self, person):
        event = self.get_birth_event(person)
        place = self.get_event_place(event)
        return self.get_place_name(place)

    def get_birth_root_place(self, person):
        event = self.get_birth_event(person)
        place = self.get_event_place(event)
        return self.get_root_place_name(place)

    def get_death_root_place(self, person):
        event = self.get_death_event(person)
        place = self.get_event_place(event)
        return self.get_root_place_name(place)

    def get_death_place(self, person):
        event = self.get_death_event(person)
        place = self.get_event_place(event)
        return self.get_place_name(place)

    def get_birth_event(self, person):
        try:
            if person is None:
                return None
            ref = person.get_birth_ref()
            if ref is None:
                return None
            return self.dbstate.db.get_event_from_handle(ref.get_reference_handle()) or None
        except Exception as e:
            print(traceback.format_exc())
            return None

    def get_death_event(self, person):
        try:
           ref = person.get_death_ref()
           if ref is None:
               return None
           return self.dbstate.db.get_event_from_handle(ref.get_reference_handle()) or None
        except Exception as e:
            print(traceback.format_exc())
            return None

    def get_death_year(self, person):
        event = self.get_death_event(person)
        return self.get_event_exact_year(event)

    def get_event_place(self, event):
        try:
            if event is None:
                return None
            place_ref = event.get_place_handle()
            if not place_ref:
                return None
            return self.dbstate.db.get_place_from_handle(place_ref) or None
        except Exception as e:
            print(traceback.format_exc())
            return None

    def get_event_exact_year(self, event):
        try:
            if event is None:
                return None
            date = event.get_date_object()
            if date and not date.is_compound():
                return date.get_year() or None
        except Exception as e:
            print(traceback.format_exc())
            pass
        return None

    def get_place_name(self, place):
        try:
            if place is None:
                return None
            name = place.get_name()
            if name is None:
                return None
            value = name.get_value()
            return value or None
        except Exception as e:
            print(traceback.format_exc())
            return None

    def build_gui(self):
        # Load UI from XML
        self.builder = Gtk.Builder()
        self.builder.add_from_file(os.path.join(os.path.dirname(__file__), "interface.xml"))
        self.builder.connect_signals(self)

        # Get the main container
        self.main_container = self.builder.get_object("main_container")


        # Get the AI recommendations label
        self.ai_recommendations_label = self.builder.get_object("ai_recommendations_label")

        # Get the TreeView from XML
        self.tree_view = self.builder.get_object("treeview")

        # Create and set the ListStore model
        self.model = Gtk.ListStore(
            str, str, str, str, str, str, str, str, GdkPixbuf.Pixbuf, GdkPixbuf.Pixbuf
        )
        self.tree_view.set_model(self.model)
        self.tree_view.set_has_tooltip(True)

        # Get selection object
        selection = self.tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)

        # Connect signals
        self.tree_view.connect("row-activated", self.on_link_clicked)
        self.tree_view.connect("query-tooltip", self.on_query_tooltip)
        self.tree_view.connect("button-press-event", self.on_button_press)

        # Get the columns from the TreeView
        columns = self.tree_view.get_columns()

        # Bind renderers to columns in ListStore
        column_icon = columns[0]
        column_icon.add_attribute(self.builder.get_object("category_icon"), "icon-name", 0)
        column_icon.add_attribute(self.builder.get_object("visited_icon"), "pixbuf", 8)
        column_icon.add_attribute(self.builder.get_object("saved_icon"), "pixbuf", 9)

        column_locale = columns[1]
        column_locale.add_attribute(self.builder.get_object("locale"), "text", 1)

        column_category = columns[2]
        column_category.add_attribute(self.builder.get_object("category"), "text", 2)

        column_link = columns[3]
        column_link.add_attribute(self.builder.get_object("url"), "text", 7)

        # Badge container
        self.badge_container = self.builder.get_object("badge_container")

        # Context menu
        self.context_menu = self.builder.get_object("context_menu")

        # Apply CSS styles
        self.apply_styles()

        return self.main_container

    def apply_styles(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(os.path.join(os.path.dirname(__file__), "assets", "style.css"))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def populate_badges(self, domain_url_pairs):
        self.badge_container.foreach(lambda widget: self.badge_container.remove(widget))
        for domain, url in domain_url_pairs:
            badge = self.create_badge(domain, url)
            self.badge_container.add(badge)
        self.badge_container.show_all()

    def create_badge(self, domain, url):
        badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        badge_box.get_style_context().add_class("badge")

        label = Gtk.Label(label=domain)
        label.get_style_context().add_class("badge-label")

        close_button = Gtk.Button(label="×")
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.set_focus_on_click(False)
        close_button.set_size_request(16, 16)
        close_button.get_style_context().add_class("badge-close")
        close_button.connect("clicked", self.on_remove_badge, badge_box)

        event_box = Gtk.EventBox()
        event_box.add(label)
        event_box.connect("button-press-event", lambda widget, event: self.open_url(url))

        badge_box.pack_start(event_box, True, True, 0)
        badge_box.pack_start(close_button, False, False, 0)

        return badge_box

    def open_url(self, url):
        webbrowser.open(url)

    def on_remove_badge(self, button, badge):
        domain_label = None
        for child in badge.get_children():
            print(f"Child: {child}")
            if isinstance(child, Gtk.EventBox):
                for sub_child in child.get_children():
                    print(f"Sub-child: {sub_child}")
                    if isinstance(sub_child, Gtk.Label):
                        domain_label = sub_child.get_text().strip()
                        print(f"Domain to skip: {domain_label}")
                        break
        if domain_label:
            self.website_loader.save_skipped_domain(domain_label)

        self.badge_container.remove(badge)

    def on_button_press(self, widget, event):
        if event.button == 3:  # Right-click mouse button
            print("on_button_press right click")
            path_info = widget.get_path_at_pos(event.x, event.y)
            if path_info:
                path, column, cell_x, cell_y = path_info
                tree_iter = self.model.get_iter(path)
                if not tree_iter or not self.model.iter_is_valid(tree_iter):
                    print("❌ Error: tree_iter is already invalid!")
                    return
                url = self.model.get_value(tree_iter, 3)
                self.context_menu = self.builder.get_object("context_menu")
                self.context_menu.active_tree_path = path
                self.context_menu.active_url = url
                print(f"save tree path: {path}")
                self.context_menu.show_all()
                self.context_menu.popup_at_pointer(event)

    def on_add_note(self, widget):
        if not self.context_menu.active_tree_path:
            print("❌ Error: No saved path to the iterator!")
            return

        print(f"self.context_menu.active_tree_path:{self.context_menu.active_tree_path}")
        tree_iter = self.get_active_tree_iter(self.context_menu.active_tree_path)
        if not tree_iter:
            print("❌ Error: tree_iter is no longer valid!")
            return

        note = Note()
        note.set(f"📌 This web link was added using the WebSearch gramplet for future reference:\n\n🔗 {self.context_menu.active_url}\n\n"
        "You can use this link to revisit the source and verify the information related to this person.")
        note.set_privacy(True)

        self.model.freeze_notify()

        with DbTxn(_("Add Web Link Note"), self.dbstate.db) as trans:
            note_handle = self.dbstate.db.add_note(note, trans)
            self.person.add_note(note_handle)
            self.dbstate.db.commit_person(self.person, trans)


        self.add_icon_event(SAVED_HASH_FILE_PATH, ICON_SAVED_PATH, tree_iter, 9)
        self.model.thaw_notify()

    def on_show_qr_code(self, widget):
        selection = self.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][3]
            qr_window = QRCodeWindow(url)
            qr_window.show_all()

    def on_copy_url_to_clipboard(self, widget):
        selection = self.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][3]
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(url, -1)
            clipboard.store()
            notification = self.show_notification(f"URL is copied to the Clipboard")
            notification.show_all()

    def show_notification(self, message):
        notification = Notification(message)
        notification.show_all()
        return notification

    def get_active_tree_iter(self, path):
        path_str = str(path)
        try:
            tree_path = Gtk.TreePath.new_from_string(path_str)
            self.tree_view.get_selection().select_path(tree_path)
            self.tree_view.set_cursor(tree_path)
            tree_iter = self.model.get_iter(tree_path)
            return tree_iter
        except Exception as e:
            print(f"❌ Error in get_active_tree_iter: {e}")
            return None

    def on_add_attribute(self, widget):
        if not self.context_menu.active_tree_path:
            print("❌ Error: No saved path to the iterator!")
            return

        tree_iter = self.model.get_iter(self.context_menu.active_tree_path)
        if not tree_iter:
            print("❌ Error: tree_iter is no longer valid!")
            return

        attribute = Attribute()
        attribute.set_type("WebSearch Link")
        attribute.set_value(self.context_menu.active_url)
        attribute.set_privacy(True)

        with DbTxn(_("Add Web Link Note"), self.dbstate.db) as trans:
            self.person.add_attribute(attribute)
            self.dbstate.db.commit_person(self.person, trans)

        self.add_icon_event(SAVED_HASH_FILE_PATH, ICON_SAVED_PATH, tree_iter, 9)

    def on_download_page(self, widget):
        pass

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        path_info = widget.get_path_at_pos(x, y)
        if path_info:
            path, column, cell_x, cell_y = path_info
            tree_iter = self.model.get_iter(path)
            category = self.model.get_value(tree_iter, 2)
            comment = self.model.get_value(tree_iter, 4) or ""

            variables_json = self.model.get_value(tree_iter, 6)
            variables = json.loads(variables_json)
            replaced_variables = [f"{key}={value}" for var in variables['replaced_variables'] for key, value in var.items()]
            empty_variables = [var for var in variables['empty_variables']]

            tooltip_text = _(f"Category: {category}\n")
            if replaced_variables:
                tooltip_text += _(f"Replaced: {', '.join(replaced_variables)}\n")
            if empty_variables:
                tooltip_text += _(f"Empty: {', '.join(empty_variables)}\n")
            if comment:
                tooltip_text += _(f"Comment: {comment}\n")
            tooltip_text = tooltip_text.rstrip()
            tooltip.set_text(tooltip_text)
            return True
        return False

    def build_options(self):
        self.opts = self.settings_ui_manager.build_options()
        list(map(self.add_option, self.opts))
        #self.settings_ui_manager.print_settings()
        #self.config_ini_manager.print_config()

    def save_options(self):
        self.config_ini_manager.set_boolean_list("websearch.enabled_files", self.opts[0].get_selected())
        self.config_ini_manager.set_enum("websearch.middle_name_handling", self.opts[1].get_value())
        self.config_ini_manager.set_boolean_option("websearch.show_short_url", self.opts[2].get_value())
        self.config_ini_manager.set_enum("websearch.url_compactness_level", self.opts[3].get_value())
        self.config_ini_manager.set_string("websearch.url_prefix_replacement", self.opts[4].get_value())
        self.config_ini_manager.set_boolean_option("websearch.use_openai", self.opts[5].get_value())
        self.config_ini_manager.set_string("websearch.openai_api_key", self.opts[6].get_value())
        self.config_ini_manager.save()

    def save_update_options(self, obj):
        self.save_options()
        self.update()
        self.on_load()
        #self.settings_ui_manager.print_settings()
        #self.config_ini_manager.print_config()

    def on_load(self):
        self.__enabled_files = self.config_ini_manager.get_list("websearch.enabled_files", DEFAULT_ENABLED_FILES)
        self.__use_openai = self.config_ini_manager.get_boolean_option("websearch.use_openai", DEFAULT_USE_OPEN_AI)
        self.__openai_api_key = self.config_ini_manager.get_string("websearch.openai_api_key")
        self.__middle_name_handling = self.config_ini_manager.get_enum("websearch.middle_name_handling", MiddleNameHandling, DEFAULT_MIDDLE_NAME_HANDLING)
        self.__show_short_url = self.config_ini_manager.get_boolean_option("websearch.show_short_url", DEFAULT_SHOW_SHORT_URL)
        self.__url_compactness_level = self.config_ini_manager.get_enum("websearch.url_compactness_level", URLCompactnessLevel, DEFAULT_URL_COMPACTNESS_LEVEL)
        self.__url_prefix_replacement = self.config_ini_manager.get_string("websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT)
