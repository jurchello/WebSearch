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
import os
import csv
import string
import re
import json
import hashlib
import traceback
import time
from enum import Enum
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.display import display_url
from gramps.gen.config import config as configman
from gramps.gen.plug.menu import BooleanListOption, EnumeratedListOption, StringOption
from gi.repository import GdkPixbuf
from gramps.gen.lib import Note, Attribute
from gramps.gen.db import DbTxn

COMMON_CSV_FILE_NAME = "common-links.csv"

# Mapping of categories to their associated icons for display
CATEGORY_ICON = {
    "Dashboard": "gramps-gramplet",
    "People": "gramps-person",
    "Relationships": "gramps-relation",
    "Families": "gramps-family",
    "Events": "gramps-event",
    "Ancestry": "gramps-pedigree",
    "Places": "gramps-place",
    "Geography": "gramps-geo",
    "Sources": "gramps-source",
    "Repositories": "gramps-repository",
    "Media": "gramps-media",
    "Notes": "gramps-notes",
    "Citations": "gramps-citation",
}
DEFAULT_CATEGORY_ICON = "gramps-gramplet"

class MiddleNameHandling(Enum):
    LEAVE_ALONE = "leave alone"  # Leave middle name unchanged
    SEPARATE = "separate"  # Separate first and middle name by space
    REMOVE = "remove"  # Remove middle name

DEFAULT_MIDDLE_NAME_HANDLING = MiddleNameHandling.REMOVE.value

class SupportedNavTypes(Enum):
    PEOPLE = "People"
    PLACES = "Places"
    SOURCES = "Sources"

class PersonDataKeys(Enum):
    GIVEN = "given"
    MIDDLE = "middle"
    SURNAME = "surname"
    BIRTH_YEAR = "birth_year"
    DEATH_YEAR = "death_year"
    BIRTH_YEAR_FROM = "birth_year_from"
    DEATH_YEAR_FROM = "death_year_from"
    BIRTH_YEAR_TO = "birth_year_to"
    DEATH_YEAR_TO = "death_year_to"
    BIRTH_PLACE = "birth_place"
    DEATH_PLACE = "death_place"
    BIRTH_ROOT_PLACE = "birth_root_place"
    DEATH_ROOT_PLACE = "death_root_place"

COMMON_LOCALE_SIGN = "★"

class CsvColumnNames(Enum):
    NAV_TYPE = "Navigation type"
    CATEGORY = "Category"
    IS_ENABLED = "Is enabled"
    URL = "URL"
    COMMENT = "Comment"

class URLCompactnessLevel(Enum):
    SHORTEST = "shortest"
    COMPACT_NO_ATTRIBUTES = "compact_no_attributes"
    COMPACT_WITH_ATTRIBUTES = "compact_with_attributes"
    LONG = "long"

DEFAULT_URL_COMPACTNESS_LEVEL = URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value

URL_PREFIXES_TO_TRIM = [
    "https://www.",
    "http://www.",
    "https://",
    "http://"
]

DEFAULT_URL_PREFIX_REPLACEMENT = "."
DEFAULT_QUERY_PARAMETERS_REPLACEMENT = "..."

VISITED_HASH_FILE_PATH = os.path.join(os.path.dirname(__file__), "visited_links.txt")
ICON_VISITED_PATH = os.path.join(os.path.dirname(__file__), "icons", "emblem-default.png")

SAVED_HASH_FILE_PATH = os.path.join(os.path.dirname(__file__), "saved_links.txt")
ICON_SAVED_PATH = os.path.join(os.path.dirname(__file__), "icons", "media-floppy.png")

ICON_SIZE = 16

class PlaceDataKeys(Enum):
    PLACE = "place"
    ROOT_PLACE = "root_place"

class SourceDataKeys(Enum):
    TITLE = "source_title"

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

class WebsiteLoader:

    CSV_DIR = os.path.join(os.path.dirname(__file__), "csv")

    @staticmethod
    def get_csv_files():
        if not os.path.exists(WebsiteLoader.CSV_DIR):
            return []

        csv_files = [os.path.join(WebsiteLoader.CSV_DIR, f) for f in os.listdir(WebsiteLoader.CSV_DIR) if f.endswith(".csv")]
        return csv_files

    @staticmethod
    def get_selected_csv_files(config):
        filtered_files = []
        csv_files = WebsiteLoader.get_csv_files()
        selected_files = config.get("websearch.enabled_files") or []
        for file in csv_files:
            file_name = os.path.basename(file)
            is_selected = file_name in selected_files
            if is_selected:
                filtered_files.append(file)
        return filtered_files

    @staticmethod
    def get_all_and_selected_files(config):
        all_files = [os.path.basename(f) for f in WebsiteLoader.get_csv_files()]
        selected_files = config.get("websearch.enabled_files") or []
        return all_files, selected_files

    @staticmethod
    def generate_hash(string: str) -> str:
        return hashlib.sha256(string.encode()).hexdigest()[:16]

    @staticmethod
    def has_hash_in_file(hash_value: str, file_path) -> bool:
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as file:
            return hash_value in file.read().splitlines()

    @staticmethod
    def save_hash_to_file(hash_value: str, file_path):
        if not WebsiteLoader.has_hash_in_file(hash_value, file_path):
            with open(file_path, "a", encoding="utf-8") as file:
                print("file.write")
                file.write(hash_value + "\n")

    @classmethod
    def load_websites(cls, config):
        websites = []
        selected_csv_files = cls.get_selected_csv_files(config)

        for selected_file_path in selected_csv_files:
            if not os.path.exists(selected_file_path):
                continue

            locale = os.path.splitext(os.path.basename(selected_file_path))[0].replace("-links", "").upper()
            if locale == "COMMON":
                locale = COMMON_LOCALE_SIGN
            with open(selected_file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                reader.fieldnames = [name.strip() if name else name for name in reader.fieldnames]

                for row in reader:

                    if not row:
                        continue

                    nav_type = row.get(CsvColumnNames.NAV_TYPE.value, "").strip()
                    category = row.get(CsvColumnNames.CATEGORY.value, "").strip()
                    is_enabled = row.get(CsvColumnNames.IS_ENABLED.value, "").strip()
                    url = row.get(CsvColumnNames.URL.value, "").strip()
                    comment = row.get(CsvColumnNames.COMMENT.value, None)

                    if not all([nav_type, category, is_enabled, url]):
                        print(f"⚠️ Some data are missing in: {selected_file_path}. A row is skipped: {row}")
                        continue

                    websites.append([nav_type, locale, category, is_enabled, url, comment])
        return websites

class WebSearch(Gramplet):

    def init(self):
        self.init_config()
        self.__enabled_files = self.config.get("websearch.enabled_files") or []
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()
        self.populate_links({}, SupportedNavTypes.PEOPLE.value)

    def init_config(self):
        _config_file = os.path.join(os.path.dirname(__file__), "WebSearch")
        if not os.path.exists(_config_file + ".ini"):
            open(_config_file + ".ini", "w").close()

        self.config = configman.register_manager(_config_file)

        self.config.register("websearch.enabled_files", [COMMON_CSV_FILE_NAME])
        self.config.register("websearch.middle_name_handling", DEFAULT_MIDDLE_NAME_HANDLING)
        self.config.register("websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT)
        self.config.register("websearch.show_short_url", True)
        self.config.register("websearch.url_compactness_level", DEFAULT_URL_COMPACTNESS_LEVEL)
        self.config.load()

    def db_changed(self):
        self.connect_signal("Person", self.active_person_changed)
        self.connect_signal("Place", self.active_place_changed)
        self.connect_signal("Source", self.active_source_changed)

    def is_true(self, value):
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    def check_pattern_variables(self, url_pattern, data):
        pattern_variables = re.findall(r"%\((.*?)\)s", url_pattern)

        replaced_variables = []
        not_found_variables = []
        empty_variables = []

        for variable in pattern_variables:
            value = data.get(variable)
            if value is None:
                not_found_variables.append(variable)
            elif value == "":
                empty_variables.append(variable)
            else:
                replaced_variables.append({variable: value})

        return {
           "replaced_variables": replaced_variables,
           "not_found_variables": not_found_variables,
           "empty_variables": empty_variables,
       }

    def populate_links(self, data, nav_type):
        self.model.clear()
        if len(data) == 0:
            return
        websites = WebsiteLoader.load_websites(self.config)

        for nav, locale, category, is_enabled, url_pattern, comment in websites:
            if nav == nav_type and self.is_true(is_enabled):
                try:
                    variables = self.check_pattern_variables(url_pattern, data)
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
                    formatted_url = self.format_url(final_url, variables)

                    hash_value = WebsiteLoader.generate_hash(final_url)

                    visited_icon = None
                    if WebsiteLoader.has_hash_in_file(hash_value, VISITED_HASH_FILE_PATH):
                        try:
                            visited_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(ICON_VISITED_PATH, ICON_SIZE, ICON_SIZE)
                        except Exception as e:
                            print(f"❌ Error loading icon: {e}")

                    saved_icon = None
                    if WebsiteLoader.has_hash_in_file(hash_value, SAVED_HASH_FILE_PATH):
                        try:
                            saved_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(ICON_SAVED_PATH, ICON_SIZE, ICON_SIZE)
                        except Exception as e:
                            print(f"❌ Error loading icon: {e}")

                    self.model.append([icon_name, locale, category, final_url, comment, url_pattern, variables_json, formatted_url, visited_icon, saved_icon])
                except KeyError:
                    print(f"{locale}. Mismatch in template variables: {url_pattern}")
                    pass

    def format_url(self, url, variables):
        show_short_url = self.config.get("websearch.show_short_url")
        if show_short_url is None:
            show_short_url = True

        compactness_level = self.config.get("websearch.url_compactness_level")
        if compactness_level is None:
            compactness_level = DEFAULT_URL_COMPACTNESS_LEVEL

        if not show_short_url:
            return url

        if compactness_level == URLCompactnessLevel.SHORTEST.value:
            return self.format_url_shortest(url, variables)
        elif compactness_level == URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value:
            return self.format_url_compact_no_attributes(url, variables)
        elif compactness_level == URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value:
            return self.format_url_compact_with_attributes(url, variables)
        elif compactness_level == URLCompactnessLevel.LONG.value:
            return self.format_url_long(url, variables)

        return url

    def format_url_shortest(self, url, variables):
        trimmed_url = self.trim_url_prefix(url)
        clean_url = self.remove_url_query_params(trimmed_url)
        return clean_url

    def format_url_compact_no_attributes(self, url, variables):
        trimmed_url = self.trim_url_prefix(url)
        clean_url = self.remove_url_query_params(trimmed_url)
        final_url = self.append_variables_to_url(clean_url, variables, False)
        return final_url

    def format_url_compact_with_attributes(self, url, variables):
        trimmed_url = self.trim_url_prefix(url)
        clean_url = self.remove_url_query_params(trimmed_url)
        final_url = self.append_variables_to_url(clean_url, variables, True)
        return final_url

    def format_url_long(self, url, variables):
        trimmed_url = self.trim_url_prefix(url)
        return trimmed_url

    def trim_url_prefix(self, url: str) -> str:
        for prefix in URL_PREFIXES_TO_TRIM:
            if url.startswith(prefix):
                replacement = self.config.get("websearch.url_prefix_replacement")
                if replacement is None:
                    replacement = DEFAULT_URL_PREFIX_REPLACEMENT
                return replacement + url[len(prefix):]
        return url

    def remove_url_query_params(self, url: str) -> str:
        return url.split('?')[0]

    def append_variables_to_url(self, url: str, variables: dict, show_attribute: bool) -> str:
        replaced_variables = variables.get('replaced_variables', [])
        if replaced_variables:
            formatted_vars = []
            for var in replaced_variables:
                for key, value in var.items():
                    if show_attribute:
                        formatted_vars.append(f"{key}={value}")
                    else:
                        formatted_vars.append(f"{value}")
            return url + DEFAULT_QUERY_PARAMETERS_REPLACEMENT + DEFAULT_QUERY_PARAMETERS_REPLACEMENT.join(formatted_vars)
        return url + DEFAULT_QUERY_PARAMETERS_REPLACEMENT

    def on_link_clicked(self, tree_view, path, column):
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, 3)
        self.add_icon_event(VISITED_HASH_FILE_PATH, ICON_VISITED_PATH, tree_iter, 8)
        display_url(url)

    def add_icon_event(self, file_path, icon_path, tree_iter, model_icon_pos):
        url = self.model.get_value(tree_iter, 3)
        hash_value = WebsiteLoader.generate_hash(url)
        if not WebsiteLoader.has_hash_in_file(hash_value, file_path):
            WebsiteLoader.save_hash_to_file(hash_value, file_path)
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
            middle_name_handling = self.config.get("websearch.middle_name_handling")

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
        print(person_data)

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
        print(place_data)

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
        print(source_data)

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
        self.model = Gtk.ListStore(
            str,                # [0]. Icon name: Represents the name of the icon to be displayed in the first column.
            str,                # [1]. Locale: Represents the locale (language or region) associated with the entry.
            str,                # [2]. Name: Represents the name or title of the entry (e.g., category name).
            str,                # [3]. URL: Represents the URL link associated with the entry.
            str,                # [4]. Comment: Represents an optional comment or description related to the entry.
            str,                # [5]. URL pattern: Represents the URL pattern associated with the entry (could be a regex pattern or template).
            str,                # [6]. Variables JSON: Represents a JSON string containing variables related to the entry (could be replaced or empty variables).
            str,                # [7]. Formatted URL: Represents the formatted URL link.
            GdkPixbuf.Pixbuf,   # [8]. Visited icon: Stores Pixbuf instead of icon name.
            GdkPixbuf.Pixbuf    # [9]. Saved icon: Stores Pixbuf instead of icon name.
        )  # ListStore: A data model to hold the information for the tree view (each column type is 'str').

        self.tree_view = Gtk.TreeView(model=self.model)

        selection = self.tree_view.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)

        self.tree_view.connect("row-activated", self.on_link_clicked)

        self.tree_view.set_has_tooltip(True)
        self.tree_view.connect("query-tooltip", self.on_query_tooltip)

        # Render a column for the icons
        renderer_category_icon = Gtk.CellRendererPixbuf()
        renderer_visited_icon = Gtk.CellRendererPixbuf()
        renderer_saved_icon = Gtk.CellRendererPixbuf()

        column_icon = Gtk.TreeViewColumn("")
        column_icon.pack_start(renderer_category_icon, False)
        column_icon.pack_start(renderer_visited_icon, False)
        column_icon.pack_start(renderer_saved_icon, False)
        column_icon.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        column_icon.add_attribute(renderer_category_icon, "icon-name", 0)
        column_icon.add_attribute(renderer_visited_icon, "pixbuf", 8)
        column_icon.add_attribute(renderer_saved_icon, "pixbuf", 9)
        column_icon.set_resizable(False)
        self.tree_view.append_column(column_icon)

        # Render a column for the locale
        renderer_text = Gtk.CellRendererText()
        column_locale = Gtk.TreeViewColumn("", renderer_text, text=1)
        column_locale.set_sort_column_id(1)
        column_locale.set_resizable(False)
        column_locale.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.tree_view.append_column(column_locale)

        # Render a column for the category name
        renderer_text = Gtk.CellRendererText()
        column_category = Gtk.TreeViewColumn(_("Category"), renderer_text, text=2)
        column_category.set_sort_column_id(2)
        column_category.set_resizable(True)
        column_category.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.tree_view.append_column(column_category)

        # Render a column for the website URL
        renderer_link = Gtk.CellRendererText()
        column_link = Gtk.TreeViewColumn(_("Website URL"), renderer_link, text=7)
        column_link.set_sort_column_id(3)
        column_link.set_resizable(True)
        column_link.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.tree_view.append_column(column_link)

        self.context_menu = Gtk.Menu()

        # Add "Add link to note" option
        add_note_item = Gtk.MenuItem("Add link to note")
        add_note_item.connect("activate", self.on_add_note)
        self.context_menu.append(add_note_item)

        # Add "Add link to attribute" option
        add_attribute_item = Gtk.MenuItem("Add link to attribute")
        add_attribute_item.connect("activate", self.on_add_attribute)
        self.context_menu.append(add_attribute_item)

        self.context_menu.show_all()

        # Add the event handler for right-click
        self.tree_view.connect("button-press-event", self.on_button_press)

        return self.tree_view

    def on_button_press(self, widget, event):
        print("on_button_press")
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
                self.context_menu.active_tree_path = path
                self.context_menu.active_url = url
                print(f"save tree path: {path}")
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
        all_files, selected_files = WebsiteLoader.get_all_and_selected_files(self.config)
        self.opts = []

        opt = BooleanListOption(_("Enable CSV Files"))
        for file in all_files:
            is_selected = file in selected_files
            opt.add_button(file, is_selected)
        self.opts.append(opt)

        middle_name_handling = EnumeratedListOption(_("Middle Name Handling"), DEFAULT_MIDDLE_NAME_HANDLING)
        for option in MiddleNameHandling:
            middle_name_handling.add_item(option.value, option.value)
        saved_value = self.config.get("websearch.middle_name_handling")
        if saved_value not in [e.value for e in MiddleNameHandling]:
            saved_value = DEFAULT_MIDDLE_NAME_HANDLING
        middle_name_handling.set_value(saved_value)
        self.opts.append(middle_name_handling)

        # Checkbox for shortened URL display
        show_short_url = BooleanListOption(_("Show Shortened URL"))
        value = self.config.get("websearch.show_short_url")
        if value is None:
            value = True
        if isinstance(value, str):
            value = value.lower() == 'true'
        show_short_url.add_button(_("Shortened URL"), value)
        self.opts.append(show_short_url)

        # Compactness level for URL display
        compactness_level = EnumeratedListOption(_("URL Compactness Level"), DEFAULT_URL_COMPACTNESS_LEVEL)
        compactness_level.add_item(URLCompactnessLevel.SHORTEST.value, _("Shortest - No Prefix, No Variables"))
        compactness_level.add_item(URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value, _("Compact - No Prefix, Variables Without Attributes (Default)"))
        compactness_level.add_item(URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value, _("Compact - No Prefix, Variables With Attributes"))
        compactness_level.add_item(URLCompactnessLevel.LONG.value, _("Long - Without Prefix on the Left"))
        saved_compactness = self.config.get("websearch.url_compactness_level")
        if saved_compactness not in [e.value for e in URLCompactnessLevel]:
             saved_compactness = DEFAULT_URL_COMPACTNESS_LEVEL
        compactness_level.set_value(saved_compactness)
        self.opts.append(compactness_level)

        # Continue with the rest of the options
        url_prefix_replacement = self.config.get("websearch.url_prefix_replacement")
        if url_prefix_replacement is None:
            url_prefix_replacement = DEFAULT_URL_PREFIX_REPLACEMENT
        opt_url_prefix = StringOption(_("URL Prefix Replacement"), url_prefix_replacement)
        self.opts.append(opt_url_prefix)

        list(map(self.add_option, self.opts))

    def save_options(self):
        self.__enabled_files = self.opts[0].get_selected()
        self.config.set("websearch.enabled_files", self.__enabled_files)

        middle_name_handling = self.opts[1].get_value()
        self.config.set("websearch.middle_name_handling", middle_name_handling)

        show_short_url = self.opts[2].get_value()
        if isinstance(show_short_url, str):
            show_short_url = show_short_url.lower() == 'true'
        self.config.set("websearch.show_short_url", show_short_url)

        compactness_level = self.opts[3].get_value()
        self.config.set("websearch.url_compactness_level", compactness_level)

        url_prefix_replacement = self.opts[4].get_value()
        self.config.set("websearch.url_prefix_replacement", url_prefix_replacement)

        self.config.save()

    def save_update_options(self, obj):
        self.save_options()
        self.update()

    def on_load(self):
        self.__enabled_files = self.config.get("websearch.enabled_files") or []
