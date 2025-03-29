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
WebSearch - a Gramplet for searching genealogical websites.

Allows searching for genealogical resources based on the active person's, place's,
or source's data. Integrates multiple regional websites into a single sidebar tool
with customizable URL templates.
"""

# Standard Python libraries
import os
import sys
import json
import traceback
import threading
import webbrowser
import urllib.parse
from enum import IntEnum
from types import SimpleNamespace
from functools import partial

# Third-party libraries
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject

# GRAMPS API
from gramps.gen.plug import Gramplet
from gramps.gui.display import display_url
from gramps.gen.lib import Note, Attribute, NoteType
from gramps.gen.db import DbTxn

# Own project imports
from entity_data_builder import EntityDataBuilder
from model_row_generator import ModelRowGenerator
from helpers import get_system_locale
from qr_window import QRCodeWindow
from openai_site_finder import OpenaiSiteFinder
from mistral_site_finder import MistralSiteFinder
from config_ini_manager import ConfigINIManager
from settings_ui_manager import SettingsUIManager
from website_loader import WebsiteLoader
from notification import Notification
from signals import WebSearchSignalEmitter
from url_formatter import UrlFormatter
from attribute_mapping_loader import AttributeMappingLoader
from attribute_links_loader import AttributeLinksLoader
from constants import (
    DEFAULT_SHOW_SHORT_URL,
    DEFAULT_URL_COMPACTNESS_LEVEL,
    DEFAULT_URL_PREFIX_REPLACEMENT,
    HIDDEN_HASH_FILE_PATH,
    USER_DATA_CSV_DIR,
    USER_DATA_JSON_DIR,
    DATA_DIR,
    CONFIGS_DIR,
    DEFAULT_ENABLED_FILES,
    DEFAULT_MIDDLE_NAME_HANDLING,
    ICON_VISITED_PATH,
    ICON_SAVED_PATH,
    VISITED_HASH_FILE_PATH,
    SAVED_HASH_FILE_PATH,
    URL_SAFE_CHARS,
    ICON_SIZE,
    INTERFACE_FILE_PATH,
    RIGHT_MOUSE_BUTTON,
    STYLE_CSS_PATH,
    DEFAULT_COLUMNS_ORDER,
    DEFAULT_SHOW_URL_COLUMN,
    DEFAULT_SHOW_VARS_COLUMN,
    DEFAULT_SHOW_USER_DATA_ICON,
    DEFAULT_SHOW_FLAG_ICONS,
    DEFAULT_SHOW_ATTRIBUTE_LINKS,
    DEFAULT_AI_PROVIDER,
    VIEW_IDS_MAPPING,
    URLCompactnessLevel,
    MiddleNameHandling,
    SupportedNavTypes,
    AIProviders,
)

MODEL_SCHEMA = [
    ("icon_name", str),
    ("locale_text", str),
    ("title", str),
    ("final_url", str),
    ("comment", str),
    ("url_pattern", str),
    ("keys_json", str),
    ("formatted_url", str),
    ("visited_icon", GdkPixbuf.Pixbuf),
    ("saved_icon", GdkPixbuf.Pixbuf),
    ("nav_type", str),
    ("visited_icon_visible", bool),
    ("saved_icon_visible", bool),
    ("obj_handle", str),
    ("replaced_keys_count", int),
    ("total_keys_count", int),
    ("keys_color", str),
    ("user_data_icon", GdkPixbuf.Pixbuf),
    ("user_data_icon_visible", bool),
    ("locale_icon", GdkPixbuf.Pixbuf),
    ("locale_icon_visible", bool),
    ("locale_text_visible", bool),
    ("display_keys_count", bool),
    ("source_type_sort", str),
]

ModelColumns = IntEnum(
    "ModelColumns", {name.upper(): idx for idx, (name, _) in enumerate(MODEL_SCHEMA)}
)
MODEL_TYPES = [type_ for _, type_ in MODEL_SCHEMA]

from translation_helper import _


class WebSearch(Gramplet):
    """
    WebSearch is a Gramplet for Gramps that provides an interface to search
    genealogy-related websites. It integrates with various online resources,
    formats search URLs based on genealogical data, and allows users to track
    visited and saved links.

    Features:
    - Fetches recommended genealogy websites based on provided data.
    - Supports both predefined CSV-based links and AI-suggested links.
    - Tracks visited and saved links with icons.
    - Allows users to add links as notes or attributes in Gramps.
    - Provides a graphical interface using GTK.
    """

    def __init__(self, gui):
        """
        Initialize the WebSearch Gramplet.

        Sets up all required components, directories, signal emitters, and configuration managers.
        Also initializes the Gramplet GUI and internal context for tracking active Gramps objects.
        """
        self._context = SimpleNamespace(
            person=None,
            family=None,
            place=None,
            source=None,
            active_url=None,
            active_tree_path=None,
            last_active_entity_handle=None,
            last_active_entity_type=None,
            previous_ai_provider=None,
        )
        self.system_locale = get_system_locale()
        self.gui = gui

        self.builder = Gtk.Builder()
        self.builder.add_from_file(INTERFACE_FILE_PATH)
        self.ui = SimpleNamespace(
            boxes=SimpleNamespace(
                main=self.builder.get_object("main_box"),
                badges=SimpleNamespace(
                    box=self.builder.get_object("badges_box"),
                    container=self.builder.get_object("badge_container"),
                ),
            ),
            ai_recommendations_label=self.builder.get_object(
                "ai_recommendations_label"
            ),
            tree_view=self.builder.get_object("treeview"),
            context_menu=self.builder.get_object("context_menu"),
            context_menu_items=SimpleNamespace(
                add_note=self.builder.get_object("add_note"),
                show_qr=self.builder.get_object("show_qr"),
                copy_link=self.builder.get_object("copy_link"),
                hide_selected=self.builder.get_object("hide_selected"),
                hide_all=self.builder.get_object("hide_all"),
            ),
            text_renderers=SimpleNamespace(
                locale=self.builder.get_object("locale_text_renderer"),
                vars_replaced=self.builder.get_object("vars_replaced_renderer"),
                slash=self.builder.get_object("slash_renderer"),
                vars_total=self.builder.get_object("vars_total_renderer"),
                title=self.builder.get_object("title_renderer"),
                url=self.builder.get_object("url_renderer"),
                comment=self.builder.get_object("comment_renderer"),
            ),
            icon_renderers=SimpleNamespace(
                category=self.builder.get_object("category_icon_renderer"),
                visited=self.builder.get_object("visited_icon_renderer"),
                saved=self.builder.get_object("saved_icon_renderer"),
                user_data=self.builder.get_object("user_data_icon_renderer"),
                locale=self.builder.get_object("locale_icon_renderer"),
            ),
            columns=SimpleNamespace(
                icons=self.builder.get_object("icons_column"),
                locale=self.builder.get_object("locale_column"),
                vars=self.builder.get_object("vars_column"),
                title=self.builder.get_object("title_column"),
                url=self.builder.get_object("url_column"),
                comment=self.builder.get_object("comment_column"),
            ),
        )

        self._columns_order = []
        self._show_url_column = False
        self._show_vars_column = False

        self.model = Gtk.ListStore(*MODEL_TYPES)

        self.make_directories()
        self.signal_emitter = WebSearchSignalEmitter()
        self.attribute_loader = AttributeMappingLoader()
        self.attribute_links_loader = AttributeLinksLoader()
        self.config_ini_manager = ConfigINIManager()
        self.settings_ui_manager = SettingsUIManager(self.config_ini_manager)
        self.website_loader = WebsiteLoader()
        self.url_formatter = UrlFormatter(self.config_ini_manager)
        Gramplet.__init__(self, gui)

    def init(self):
        """Initializes and attaches the main GTK interface to the gramplet container."""
        self.gui.WIDGET = self.build_gui()
        container = self.gui.get_container_widget()
        if self.gui.textview in container.get_children():
            container.remove(self.gui.textview)
        container.add(self.gui.WIDGET)
        self.gui.WIDGET.show_all()

    def post_init(self):
        """Initializes GUI signals and refreshes the AI section."""
        self.signal_emitter.connect("sites-fetched", self.on_sites_fetched)
        self.refresh_ai_section()

    def refresh_ai_section(self):
        """Updates AI provider settings and fetches AI-recommended sites if necessary."""
        locales, domains, include_global = self.website_loader.get_domains_data(
            self.config_ini_manager
        )

        self.toggle_badges_visibility()

        if self._ai_provider == AIProviders.DISABLED.value:
            return

        if not self._ai_api_key:
            print("❌ ERROR: No AI API Key found.", file=sys.stderr)
            return

        if self._context.previous_ai_provider == self._ai_provider:
            return
        self._context.previous_ai_provider = self._ai_provider

        if self._ai_provider == AIProviders.OPENAI.value:
            self.finder = OpenaiSiteFinder(self._ai_api_key, self._ai_model)
        elif self._ai_provider == AIProviders.MISTRAL.value:
            self.finder = MistralSiteFinder(self._ai_api_key, self._ai_model)
        else:
            print(f"⚠ Unknown AI provider: {self._ai_provider}", file=sys.stderr)
            return

        threading.Thread(
            target=self.fetch_sites_in_background,
            args=(domains, locales, include_global),
            daemon=True,
        ).start()

    def make_directories(self):
        """Creates necessary directories for storing configurations and user data."""
        for directory in [DATA_DIR, CONFIGS_DIR, USER_DATA_CSV_DIR, USER_DATA_JSON_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

    def fetch_sites_in_background(self, csv_domains, locales, include_global):
        """Fetches AI-recommended genealogy sites in a background thread."""
        skipped_domains = self.website_loader.load_skipped_domains()
        all_excluded_domains = csv_domains.union(skipped_domains)
        try:
            results = self.finder.find_sites(
                all_excluded_domains, locales, include_global
            )
            GObject.idle_add(self.signal_emitter.emit, "sites-fetched", results)
        except Exception as e:
            print(f"❌ Error fetching sites: {e}", file=sys.stderr)
            GObject.idle_add(self.signal_emitter.emit, "sites-fetched", None)

    def on_sites_fetched(self, gramplet, results):
        """
        Handles the 'sites-fetched' signal and populates badges if valid results are received.
        """
        if results:
            try:
                sites = json.loads(results)
                if not isinstance(sites, list):
                    return
                domain_url_pairs = [
                    (site.get("domain", "").strip(), site.get("url", "").strip())
                    for site in sites
                    if site.get("domain") and site.get("url")
                ]
                if domain_url_pairs:
                    self.populate_badges(domain_url_pairs)
            except json.JSONDecodeError as e:
                print(f"❌ JSON Decode Error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"❌ Error processing sites: {e}", file=sys.stderr)

    def db_changed(self):

        """Responds to changes in the database and updates the active context accordingly."""
        self.entity_data_builder = EntityDataBuilder(self.dbstate, self.config_ini_manager)
        self.model_row_generator = ModelRowGenerator(
            SimpleNamespace(
                website_loader=self.website_loader,
                url_formatter=self.url_formatter,
                attribute_loader=self.attribute_loader,
                config_ini_manager=self.config_ini_manager,
            )
        )

        self.connect_signal("Person", self.active_person_changed)
        self.connect_signal("Place", self.active_place_changed)
        self.connect_signal("Source", self.active_source_changed)
        self.connect_signal("Family", self.active_family_changed)
        self.connect_signal("Event", self.active_event_changed)
        self.connect_signal("Citation", self.active_citation_changed)
        self.connect_signal("Media", self.active_media_changed)

        self.dbstate.db.connect("person-update", self.on_person_update)
        self.dbstate.db.connect("place-update", self.on_place_update)
        self.dbstate.db.connect("source-update", self.on_source_update)
        self.dbstate.db.connect("family-update", self.on_family_update)
        self.dbstate.db.connect("event-update", self.on_event_update)
        self.dbstate.db.connect("citation-update", self.on_citation_update)
        self.dbstate.db.connect("media-update", self.on_media_update)


        active_person_handle = self.gui.uistate.get_active("Person")
        active_place_handle = self.gui.uistate.get_active("Place")
        active_source_handle = self.gui.uistate.get_active("Source")
        active_family_handle = self.gui.uistate.get_active("Family")
        active_event_handle = self.gui.uistate.get_active("Event")
        active_citation_handle = self.gui.uistate.get_active("Citation")
        active_media_handle = self.gui.uistate.get_active("Media")

        if active_person_handle:
            self.active_person_changed(active_person_handle)
        elif active_place_handle:
            self.active_place_changed(active_place_handle)
        elif active_source_handle:
            self.active_source_changed(active_source_handle)
        elif active_family_handle:
            self.active_family_changed(active_family_handle)
        elif active_event_handle:
            self.active_event_changed(active_event_handle)
        elif active_citation_handle:
            self.active_citation_changed(active_citation_handle)
        elif active_media_handle:
            self.active_media_changed(active_media_handle)

        notebook = self.gui.uistate.viewmanager.notebook
        if notebook:
            notebook.connect("switch-page", self.on_category_changed)

    def on_person_update(self, handle, *args):
        print("Person updated, handle:", handle)
        # Завантажте об’єкт або виконайте іншу логіку
        #person_obj = self.dbstate.db.get_person_from_handle(handle)
        # Викликаємо ваш метод оновлення, якщо потрібно
        #self.active_person_changed(handle)

    def on_place_update(self, handle, *args):
        print("Place updated, handle:", handle)
        #self.active_place_changed(handle)

    def on_source_update(self, handle, *args):
        print("Source updated, handle:", handle)
        #self.active_source_changed(handle)

    def on_family_update(self, handle, *args):
        print("Family updated, handle:", handle)
        #self.active_family_changed(handle)

    def on_event_update(self, handle, *args):
        print("Event updated, handle:", handle)
        #self.active_event_changed(handle)

    def on_citation_update(self, handle, *args):
        print("Citation updated, handle:", handle)
        #self.active_citation_changed(handle)

    def on_media_update(self, handle, *args):
        print("Media updated, handle:", handle)
        #self.active_media_changed(handle)


    def on_category_changed(self, notebook, page, page_num, *args):
        try:
            page_lookup = self.gui.uistate.viewmanager.page_lookup
            for (cat_num, view_num), p_num in page_lookup.items():
                if p_num == page_num:
                    views = self.gui.uistate.viewmanager.views
                    view_id = views[cat_num][view_num][0].id
                    nav_type = VIEW_IDS_MAPPING.get(view_id, None)
                    if nav_type:
                        self._context.last_active_entity_type = nav_type
                        self._context.last_active_entity_handle = self.gui.uistate.get_active(nav_type)
                        self.call_entity_changed_method()
                    else:
                        self.model.clear()
                    break
        except Exception:
            self.model.clear()

    def populate_links(self, core_keys, attribute_keys, nav_type, obj):
        """Populates the list model with formatted website links relevant to the current entity."""
        self.model.clear()
        websites = self.website_loader.load_websites(self.config_ini_manager)

        if self._show_attribute_links:
            attr_websites = self.attribute_links_loader.get_links_from_attributes(
                obj, nav_type
            )
            websites += attr_websites

        common_data = (core_keys, attribute_keys, nav_type, obj)
        for website_data in websites:
            model_row = self.model_row_generator.generate(common_data, website_data)
            if model_row:
                self.model.append([model_row[name] for name, _ in MODEL_SCHEMA])

    def on_link_clicked(self, tree_view, path, column):
        """Handles the event when a URL is clicked in the tree view and opens the link."""
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
        encoded_url = urllib.parse.quote(url, safe=URL_SAFE_CHARS)
        self.add_icon_event(
            SimpleNamespace(
                file_path=VISITED_HASH_FILE_PATH,
                icon_path=ICON_VISITED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.VISITED_ICON.value,
                model_visibility_pos=ModelColumns.VISITED_ICON_VISIBLE.value,
            )
        )
        display_url(encoded_url)

    def add_icon_event(self, settings):
        """Adds a visual icon to the model and saves the hash when a link is clicked."""
        file_path = settings.file_path
        icon_path = settings.icon_path
        tree_iter = settings.tree_iter
        model_icon_pos = settings.model_icon_pos
        model_visibility_pos = settings.model_visibility_pos
        url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
        obj_handle = self.model.get_value(tree_iter, ModelColumns.OBJ_HANDLE.value)
        hash_value = self.website_loader.generate_hash(f"{url}|{obj_handle}")
        if not self.website_loader.has_hash_in_file(hash_value, file_path):
            self.website_loader.save_hash_to_file(hash_value, file_path)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    icon_path, ICON_SIZE, ICON_SIZE
                )
                self.model.set_value(tree_iter, model_icon_pos, pixbuf)
                self.model.set_value(tree_iter, model_visibility_pos, True)
                self.ui.columns.icons.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
                self.ui.columns.icons.set_fixed_width(-1)
                self.ui.columns.icons.queue_resize()
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)

    def active_person_changed(self, handle):
        """Handles updates when the active person changes in the GUI."""
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = 'Person'
        self.close_context_menu()

        person = self.dbstate.db.get_person_from_handle(handle)
        self._context.person = person
        if not person:
            return

        person_data, attribute_keys = self.entity_data_builder.get_person_data(person)
        self.populate_links(
            person_data, attribute_keys, SupportedNavTypes.PEOPLE.value, person
        )
        self.update()

    def active_event_changed(self, handle):
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = 'Event'
        """Handles updates when the active event changes in the GUI."""
        self.close_context_menu()

        event = self.dbstate.db.get_event_from_handle(handle)
        self._context.event = event
        if not event:
            return

        self.populate_links({}, {}, SupportedNavTypes.EVENTS.value, event)
        self.update()

    def active_citation_changed(self, handle):
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = 'Citation'
        """Handles updates when the active citation changes in the GUI."""
        self.close_context_menu()

        citation = self.dbstate.db.get_citation_from_handle(handle)
        self._context.citation = citation
        if not citation:
            return

        self.populate_links({}, {}, SupportedNavTypes.CITATIONS.value, citation)
        self.update()

    def active_media_changed(self, handle):
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = 'Media'
        """Handles updates when the active media changes in the GUI."""
        self.close_context_menu()

        media = self.dbstate.db.get_media_from_handle(handle)
        self._context.media = media
        if not media:
            return

        self.populate_links({}, {}, SupportedNavTypes.MEDIA.value, media)
        self.update()

    def active_place_changed(self, handle):
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = 'Place'
        """Handles updates when the active place changes in the GUI."""
        try:
            place = self.dbstate.db.get_place_from_handle(handle)
            self._context.place = place
            if not place:
                return

            place_data = self.entity_data_builder.get_place_data(place)
            self.populate_links(place_data, {}, SupportedNavTypes.PLACES.value, place)
            self.update()
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)

    def active_source_changed(self, handle):
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = 'Source'
        """Handles updates when the active source changes in the GUI."""
        source = self.dbstate.db.get_source_from_handle(handle)
        self._context.source = source
        if not source:
            return

        source_data = self.entity_data_builder.get_source_data(source)
        self.populate_links(source_data, {}, SupportedNavTypes.SOURCES.value, source)
        self.update()

    def active_family_changed(self, handle):
        self._context.last_active_entity_handle = handle
        self._context.last_active_entity_type = 'Family'
        """Handles updates when the active family changes in the GUI."""
        family = self.dbstate.db.get_family_from_handle(handle)
        self._context.family = family
        if not family:
            return

        family_data = self.entity_data_builder.get_family_data(family)
        self.populate_links(family_data, {}, SupportedNavTypes.FAMILIES.value, family)
        self.update()

    def close_context_menu(self):
        """Closes the context menu if it is currently visible."""
        if self.ui.context_menu and self.ui.context_menu.get_visible():
            self.ui.context_menu.hide()

    def build_gui(self):
        """Constructs and returns the full GTK UI for the WebSearch Gramplet."""

        self.builder.connect_signals(self)

        # Create and set the ListStore model
        self.ui.tree_view.set_model(self.model)
        self.ui.tree_view.set_has_tooltip(True)

        # Get selection object
        selection = self.ui.tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)

        # Connect signals
        self.ui.tree_view.connect("row-activated", self.on_link_clicked)
        self.ui.tree_view.connect("query-tooltip", self.on_query_tooltip)
        self.ui.tree_view.connect("button-press-event", self.on_button_press)
        self.ui.tree_view.connect("columns-changed", self.on_column_changed)

        # Columns reordering
        for column in self.ui.tree_view.get_columns():
            column.set_reorderable(True)

        # Columns sorting
        self.add_sorting(self.ui.columns.locale, ModelColumns.SOURCE_TYPE_SORT.value)
        self.add_sorting(self.ui.columns.title, ModelColumns.TITLE.value)
        self.add_sorting(self.ui.columns.url, ModelColumns.FORMATTED_URL.value)
        self.add_sorting(self.ui.columns.comment, ModelColumns.COMMENT.value)

        # Columns rendering
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.category, "icon-name", ModelColumns.ICON_NAME.value
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.visited, "pixbuf", ModelColumns.VISITED_ICON.value
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.visited,
            "visible",
            ModelColumns.VISITED_ICON_VISIBLE.value,
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.saved, "pixbuf", ModelColumns.SAVED_ICON.value
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.saved,
            "visible",
            ModelColumns.SAVED_ICON_VISIBLE.value,
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.user_data,
            "pixbuf",
            ModelColumns.USER_DATA_ICON.value,
        )
        self.ui.columns.icons.add_attribute(
            self.ui.icon_renderers.user_data,
            "visible",
            ModelColumns.USER_DATA_ICON_VISIBLE.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_replaced,
            "text",
            ModelColumns.REPLACED_KEYS_COUNT.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_total,
            "text",
            ModelColumns.TOTAL_KEYS_COUNT.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_replaced,
            "foreground",
            ModelColumns.KEYS_COLOR.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_replaced,
            "visible",
            ModelColumns.DISPLAY_KEYS_COUNT.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.vars_total,
            "visible",
            ModelColumns.DISPLAY_KEYS_COUNT.value,
        )
        self.ui.columns.vars.add_attribute(
            self.ui.text_renderers.slash,
            "visible",
            ModelColumns.DISPLAY_KEYS_COUNT.value,
        )
        self.ui.text_renderers.vars_total.set_property("foreground", "green")
        self.ui.columns.locale.add_attribute(
            self.ui.text_renderers.locale, "text", ModelColumns.LOCALE_TEXT.value
        )
        self.ui.columns.locale.add_attribute(
            self.ui.text_renderers.locale,
            "visible",
            ModelColumns.LOCALE_TEXT_VISIBLE.value,
        )
        self.ui.columns.locale.add_attribute(
            self.ui.icon_renderers.locale, "pixbuf", ModelColumns.LOCALE_ICON.value
        )
        self.ui.columns.locale.add_attribute(
            self.ui.icon_renderers.locale,
            "visible",
            ModelColumns.LOCALE_ICON_VISIBLE.value,
        )
        self.ui.columns.title.add_attribute(
            self.ui.text_renderers.title, "text", ModelColumns.TITLE.value
        )
        self.ui.columns.url.add_attribute(
            self.ui.text_renderers.url, "text", ModelColumns.FORMATTED_URL.value
        )
        self.ui.columns.comment.add_attribute(
            self.ui.text_renderers.comment, "text", ModelColumns.COMMENT.value
        )

        # CSS styles, translate, update
        self.apply_styles()
        self.translate()
        self.update_url_column_visibility()
        self.update_keys_column_visibility()
        self.reorder_columns()

        return self.ui.boxes.main

    def reorder_columns(self):
        """Reorders the treeview columns based on user configuration."""
        self._columns_order = self.config_ini_manager.get_list(
            "websearch.columns_order", DEFAULT_COLUMNS_ORDER
        )

        columns_map = self.ui.columns
        previous_column = None

        for column_id in self._columns_order:
            column = getattr(columns_map, column_id, None)
            if column:
                current_pos = self.ui.tree_view.get_columns().index(column)
                expected_pos = self._columns_order.index(column_id)
                if current_pos != expected_pos:
                    self.ui.tree_view.move_column_after(column, previous_column)
                previous_column = column

    def on_column_changed(self, tree_view):
        """Saves the current order of columns when changed by the user."""
        columns = tree_view.get_columns()
        column_map = {v: k for k, v in self.ui.columns.__dict__.items()}
        columns_order = [column_map[col] for col in columns]
        self.config_ini_manager.set_list("websearch.columns_order", columns_order)

    def update_url_column_visibility(self):
        """Updates the visibility of the 'Website URL' column."""
        self._show_url_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_url_column", DEFAULT_SHOW_URL_COLUMN
        )
        self.ui.columns.url.set_visible(self._show_url_column)

    def update_keys_column_visibility(self):
        """Updates the visibility of the 'Keys' column."""
        self._show_vars_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_vars_column", DEFAULT_SHOW_VARS_COLUMN
        )
        self.ui.columns.vars.set_visible(self._show_vars_column)

    def translate(self):
        """Sets translated text for UI elements and context menu."""
        self.ui.columns.locale.set_title("")
        self.ui.columns.vars.set_title(_("Keys"))
        self.ui.columns.title.set_title(_("Title"))
        self.ui.columns.url.set_title(_("Website URL"))
        self.ui.columns.comment.set_title(_("Comment"))

        self.ui.context_menu_items.add_note.set_label(_("Add link to note"))
        self.ui.context_menu_items.show_qr.set_label(_("Show QR-code"))
        self.ui.context_menu_items.copy_link.set_label(_("Copy link to clipboard"))
        self.ui.context_menu_items.hide_selected.set_label(
            _("Hide link for selected item")
        )
        self.ui.context_menu_items.hide_all.set_label(_("Hide link for all items"))

        self.ui.ai_recommendations_label.set_text(_("🔍 AI Suggestions"))

    def toggle_badges_visibility(self):
        """Shows or hides the badge container based on OpenAI usage."""
        if self._ai_provider != AIProviders.DISABLED.value:
            self.ui.boxes.badges.box.show()
        else:
            self.ui.boxes.badges.box.hide()

    def add_sorting(self, column, index):
        """Enables sorting for the specified column."""
        column.set_sort_column_id(index)
        self.model.set_sort_column_id(index, Gtk.SortType.ASCENDING)

    def apply_styles(self):
        """Applies custom CSS styling to the WebSearch interface."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(STYLE_CSS_PATH)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def populate_badges(self, domain_url_pairs):
        """Displays AI-suggested site badges in the interface."""
        self.ui.boxes.badges.container.foreach(self.remove_widget)
        for domain, url in domain_url_pairs:
            badge = self.create_badge(domain, url)
            self.ui.boxes.badges.container.add(badge)
        self.ui.boxes.badges.container.show_all()

    def remove_widget(self, widget):
        """Removes a widget from the container."""
        self.ui.boxes.badges.container.remove(widget)

    def create_badge(self, domain, url):
        """Creates a clickable badge widget for an AI-suggested domain."""
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
        event_box.connect("button-press-event", self.on_button_press_event, url)

        badge_box.pack_start(event_box, True, True, 0)
        badge_box.pack_start(close_button, False, False, 0)

        return badge_box

    def on_button_press_event(self, widget, event, url):
        """Handles button press event to open a URL."""
        self.open_url(url)

    def open_url(self, url):
        """Opens the given URL in the default web browser."""
        webbrowser.open(urllib.parse.quote(url, safe=URL_SAFE_CHARS))

    def on_remove_badge(self, button, badge):
        """Handles removing a badge and saving its domain to skipped list."""
        domain_label = None
        for child in badge.get_children():
            if isinstance(child, Gtk.EventBox):
                for sub_child in child.get_children():
                    if isinstance(sub_child, Gtk.Label):
                        domain_label = sub_child.get_text().strip()
                        break
        if domain_label:
            self.website_loader.save_skipped_domain(domain_label)

        self.ui.boxes.badges.container.remove(badge)

    def on_button_press(self, widget, event):
        """Handles right-click context menu activation in the treeview."""
        if event.button == RIGHT_MOUSE_BUTTON:
            path_info = widget.get_path_at_pos(event.x, event.y)
            if path_info:
                path, column, cell_x, cell_y = path_info
                tree_iter = self.model.get_iter(path)
                if not tree_iter or not self.model.iter_is_valid(tree_iter):
                    return
                url = self.model.get_value(tree_iter, ModelColumns.FINAL_URL.value)
                nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)

                self._context.active_tree_path = path
                self._context.active_url = url
                self.ui.context_menu.show_all()
                # add_attribute_item = self.builder.get_object("AddAttribute")

                if nav_type == SupportedNavTypes.PEOPLE.value:
                    # add_attribute_item.show()
                    self.ui.context_menu_items.add_note.show()
                else:
                    # add_attribute_item.hide()
                    self.ui.context_menu_items.add_note.hide()

                self.ui.context_menu.popup_at_pointer(event)

    def on_add_note(self, widget):
        """Adds the current selected URL as a note to the person record."""
        if not self._context.active_tree_path:
            print("❌ Error: No saved path to the iterator!", file=sys.stderr)
            return

        note = Note()
        note.set(
            _(
                "📌 This web link was added using the WebSearch gramplet for future reference:\n\n"
                "🔗 {url}\n\nYou can use this link to revisit the source and verify the "
                "information related to this person."
            ).format(url=self._context.active_url)
        )

        note.set_privacy(True)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)
        note_handle = None

        with DbTxn(_("Add Web Link Note"), self.dbstate.db) as trans:
            if nav_type == SupportedNavTypes.PEOPLE.value:
                note.set_type(NoteType.PERSON)
                note_handle = self.dbstate.db.add_note(note, trans)
                self._context.person.add_note(note_handle)
                self.dbstate.db.commit_person(self._context.person, trans)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        self.add_icon_event(
            SimpleNamespace(
                file_path=SAVED_HASH_FILE_PATH,
                icon_path=ICON_SAVED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.SAVED_ICON.value,
                model_visibility_pos=ModelColumns.SAVED_ICON_VISIBLE.value,
            )
        )

        try:
            note_obj = self.dbstate.db.get_note_from_handle(note_handle)
            note_gramps_id = note_obj.get_gramps_id()
            notification = self.show_notification(
                _("Note #%(id)s has been successfully added") % {"id": note_gramps_id}
            )
            notification.show_all()
        except Exception:
            notification = self.show_notification(_("Error creating note"))
            notification.show_all()


    def on_show_qr_code(self, widget):
        """Opens a window showing the QR code for the selected URL."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][ModelColumns.FINAL_URL.value]
            qr_window = QRCodeWindow(url)
            qr_window.show_all()

    def on_copy_url_to_clipboard(self, widget):
        """Copies the selected URL to the system clipboard."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url = model[tree_iter][ModelColumns.FINAL_URL.value]
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(url, -1)
            clipboard.store()
            notification = self.show_notification(_("URL is copied to the Clipboard"))
            notification.show_all()

    def on_hide_link_for_selected_item(self, widget):
        """Hides the selected link only for the current Gramps object."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url_pattern = model[tree_iter][ModelColumns.URL_PATTERN.value]
            obj_handle = model[tree_iter][ModelColumns.OBJ_HANDLE.value]
            nav_type = model[tree_iter][ModelColumns.NAV_TYPE.value]
            if not self.website_loader.has_string_in_file(
                f"{url_pattern}|{obj_handle}|{nav_type}", HIDDEN_HASH_FILE_PATH
            ):
                self.website_loader.save_string_to_file(
                    f"{url_pattern}|{obj_handle}|{nav_type}", HIDDEN_HASH_FILE_PATH
                )
            model.remove(tree_iter)

    def on_hide_link_for_all_items(self, widget):
        """Hides the selected link for all Gramps objects."""
        selection = self.ui.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            url_pattern = model[tree_iter][ModelColumns.URL_PATTERN.value]
            nav_type = model[tree_iter][ModelColumns.NAV_TYPE.value]
            if not self.website_loader.has_string_in_file(
                f"{url_pattern}|{nav_type}", HIDDEN_HASH_FILE_PATH
            ):
                self.website_loader.save_string_to_file(
                    f"{url_pattern}|{nav_type}", HIDDEN_HASH_FILE_PATH
                )
            model.remove(tree_iter)

    def show_notification(self, message):
        """Displays a floating notification with the given message."""
        notification = Notification(message)
        notification.show_all()
        return notification

    def get_active_tree_iter(self, path):
        """Returns the tree iter for the given tree path."""
        path_str = str(path)
        try:
            tree_path = Gtk.TreePath.new_from_string(path_str)
            self.ui.tree_view.get_selection().select_path(tree_path)
            self.ui.tree_view.set_cursor(tree_path)
            tree_iter = self.model.get_iter(tree_path)
            return tree_iter
        except Exception as e:
            print(f"❌ Error in get_active_tree_iter: {e}", file=sys.stderr)
            return None

    def on_add_attribute(self, widget):
        """(Unused) Adds the selected URL as an attribute to the person."""
        if not self._context.active_tree_path:
            print("❌ Error: No saved path to the iterator!", file=sys.stderr)
            return

        attribute = Attribute()
        attribute.set_type(_("WebSearch Link"))
        attribute.set_value(self._context.active_url)
        attribute.set_privacy(True)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        nav_type = self.model.get_value(tree_iter, ModelColumns.NAV_TYPE.value)

        # with DbTxn(_("Add Web Link Attribute"), self.dbstate.db) as trans:
        #    if nav_type == SupportedNavTypes.PEOPLE.value:
        #        self._context.person.add_attribute(attribute)
        #        self.dbstate.db.commit_person(self._context.person, trans)

        tree_iter = self.get_active_tree_iter(self._context.active_tree_path)
        self.add_icon_event(
            SimpleNamespace(
                file_path=SAVED_HASH_FILE_PATH,
                icon_path=ICON_SAVED_PATH,
                tree_iter=tree_iter,
                model_icon_pos=ModelColumns.SAVED_ICON.value,
                model_visibility_pos=ModelColumns.SAVED_ICON_VISIBLE.value,
            )
        )

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """Displays a tooltip with key and comment information."""
        bin_x, bin_y = widget.convert_widget_to_bin_window_coords(x, y)
        path_info = widget.get_path_at_pos(bin_x, bin_y)

        if path_info:
            path, column, cell_x, cell_y = path_info
            tree_iter = self.model.get_iter(path)
            title = self.model.get_value(tree_iter, ModelColumns.TITLE.value)
            comment = self.model.get_value(tree_iter, ModelColumns.COMMENT.value) or ""

            keys_json = self.model.get_value(tree_iter, ModelColumns.KEYS_JSON.value)
            keys = json.loads(keys_json)
            replaced_keys = [
                f"{key}={value}"
                for var in keys["replaced_keys"]
                for key, value in var.items()
            ]
            empty_keys = list(keys["empty_keys"])

            tooltip_text = _("Title: {title}\n").format(title=title)
            if replaced_keys:
                tooltip_text += _("Replaced: {keys}\n").format(
                    keys=", ".join(replaced_keys)
                )
            if empty_keys:
                tooltip_text += _("Empty: {keys}\n").format(keys=", ".join(empty_keys))
            if comment:
                tooltip_text += _("Comment: {comment}\n").format(comment=comment)
            tooltip_text = tooltip_text.rstrip()
            tooltip.set_text(tooltip_text)
            return True
        return False

    def build_options(self):
        """Builds the list of configurable options for the Gramplet."""
        self.opts = self.settings_ui_manager.build_options()
        list(map(self.add_option, self.opts))

    def save_options(self):
        """Saves the current state of the configuration options."""
        self.config_ini_manager.set_boolean_list(
            "websearch.enabled_files", self.opts[0].get_selected()
        )
        self.config_ini_manager.set_enum(
            "websearch.middle_name_handling", self.opts[1].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_short_url", self.opts[2].get_value()
        )
        self.config_ini_manager.set_enum(
            "websearch.url_compactness_level", self.opts[3].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.url_prefix_replacement", self.opts[4].get_value()
        )

        self.config_ini_manager.set_enum(
            "websearch.ai_provider", self.opts[5].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.openai_api_key", self.opts[6].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.openai_model", self.opts[7].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.mistral_api_key", self.opts[8].get_value()
        )
        self.config_ini_manager.set_string(
            "websearch.mistral_model", self.opts[9].get_value()
        )

        self.config_ini_manager.set_boolean_option(
            "websearch.show_url_column", self.opts[10].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_vars_column", self.opts[11].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_user_data_icon", self.opts[12].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_flag_icons", self.opts[13].get_value()
        )
        self.config_ini_manager.set_boolean_option(
            "websearch.show_attribute_links", self.opts[14].get_value()
        )
        self.config_ini_manager.save()

    def save_update_options(self, obj):
        """Saves configuration options and refreshes the Gramplet view."""
        self.save_options()
        self.update()
        self.on_load()
        self.update_url_column_visibility()
        self.update_keys_column_visibility()
        self.call_entity_changed_method()
        self.refresh_ai_section()

    def call_entity_changed_method(self):
        """Calls the entity changed method based on the last active entity type."""
        entity_type = self._context.last_active_entity_type.lower()
        method_name = f"active_{entity_type}_changed"
        method = getattr(self, method_name, None)
        if method:
            method(self._context.last_active_entity_handle)

    def on_load(self):
        """Loads all persistent WebSearch configuration settings."""
        self._enabled_files = self.config_ini_manager.get_list(
            "websearch.enabled_files", DEFAULT_ENABLED_FILES
        )
        self._ai_provider = self.load_ai_provider()

        self._openai_api_key = self.config_ini_manager.get_string(
            "websearch.openai_api_key", ""
        )
        self._openai_model = self.config_ini_manager.get_string(
            "websearch.openai_model", ""
        )

        self._mistral_api_key = self.config_ini_manager.get_string(
            "websearch.mistral_api_key", ""
        )
        self._mistral_model = self.config_ini_manager.get_string(
            "websearch.mistral_model", ""
        )

        if self._ai_provider == AIProviders.OPENAI.value:
            self._ai_api_key = self._openai_api_key
            self._ai_model = self._openai_model
        if self._ai_provider == AIProviders.MISTRAL.value:
            self._ai_api_key = self._mistral_api_key
            self._ai_model = self._mistral_model
        elif self._ai_provider == AIProviders.DISABLED.value:
            self._ai_api_key = ""
            self._ai_model = ""

        self._middle_name_handling = self.config_ini_manager.get_enum(
            "websearch.middle_name_handling",
            MiddleNameHandling,
            DEFAULT_MIDDLE_NAME_HANDLING,
        )
        self._show_short_url = self.config_ini_manager.get_boolean_option(
            "websearch.show_short_url", DEFAULT_SHOW_SHORT_URL
        )
        self._url_compactness_level = self.config_ini_manager.get_enum(
            "websearch.url_compactness_level",
            URLCompactnessLevel,
            DEFAULT_URL_COMPACTNESS_LEVEL,
        )
        self._url_prefix_replacement = self.config_ini_manager.get_string(
            "websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT
        )
        self._show_url_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_url_column", DEFAULT_SHOW_URL_COLUMN
        )
        self._show_vars_column = self.config_ini_manager.get_boolean_option(
            "websearch.show_vars_column", DEFAULT_SHOW_VARS_COLUMN
        )
        self._show_user_data_icon = self.config_ini_manager.get_boolean_option(
            "websearch.show_user_data_icon", DEFAULT_SHOW_USER_DATA_ICON
        )
        self._show_flag_icons = self.config_ini_manager.get_boolean_option(
            "websearch.show_flag_icons", DEFAULT_SHOW_FLAG_ICONS
        )
        self._show_attribute_links = self.config_ini_manager.get_boolean_option(
            "websearch.show_attribute_links", DEFAULT_SHOW_ATTRIBUTE_LINKS
        )
        self._columns_order = self.config_ini_manager.get_list(
            "websearch.columns_order", DEFAULT_COLUMNS_ORDER
        )

    def load_ai_provider(self):
        return self.config_ini_manager.get_enum(
            "websearch.ai_provider",
            AIProviders,
            DEFAULT_AI_PROVIDER,
        )
