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
from gramps.gen.plug.menu import BooleanListOption, EnumeratedListOption

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
        self.config.load()

    def post_init(self):
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
                    self.model.append([icon_name, locale, category, final_url, comment, url_pattern, variables_json])
                except KeyError:
                    print(f"{locale}. Mismatch in template variables: {url_pattern}")
                    pass

    def on_link_clicked(self, tree_view, path, column):
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, 3)
        display_url(url)

    def active_person_changed(self, handle):
        person = self.dbstate.db.get_person_from_handle(handle)
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
            ref = person.get_birth_ref()
            return self.dbstate.db.get_event_from_handle(ref.get_reference_handle()) or None
        except Exception as e:
            print(traceback.format_exc())
            return None

    def get_death_event(self, person):
        try:
           ref = person.get_death_ref()
           return self.dbstate.db.get_event_from_handle(ref.get_reference_handle()) or None
        except Exception as e:
            print(traceback.format_exc())
            return None

    def get_death_year(self, person):
        event = self.get_death_event(person)
        return self.get_event_exact_year(event)

    def get_event_place(self, event):
        try:
            place_ref = event.get_place_handle()
            if not place_ref:
                return None
            return self.dbstate.db.get_place_from_handle(place_ref) or None
        except Exception as e:
            print(traceback.format_exc())
            return None

    def get_event_exact_year(self, event):
        try:
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
            str,  # [0]. Icon name: Represents the name of the icon to be displayed in the first column.
            str,  # [1]. Locale: Represents the locale (language or region) associated with the entry.
            str,  # [2]. Name: Represents the name or title of the entry (e.g., category name).
            str,  # [3]. URL: Represents the URL link associated with the entry.
            str,  # [4]. Comment: Represents an optional comment or description related to the entry.
            str,  # [5]. URL pattern: Represents the URL pattern associated with the entry (could be a regex pattern or template).
            str   # [6]. Variables JSON: Represents a JSON string containing variables related to the entry (could be replaced or empty variables).
        )  # ListStore: A data model to hold the information for the tree view (each column type is 'str').

        tree_view = Gtk.TreeView(model=self.model)
        tree_view.connect("row-activated", self.on_link_clicked)

        tree_view.set_has_tooltip(True)
        tree_view.connect("query-tooltip", self.on_query_tooltip)

        # Render a column for the icon
        renderer_icon = Gtk.CellRendererPixbuf()
        column_icon = Gtk.TreeViewColumn("", renderer_icon)
        column_icon.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        column_icon.add_attribute(renderer_icon, "icon-name", 0)
        column_icon.set_resizable(False)
        tree_view.append_column(column_icon)

        # Render a column for the locale
        renderer_text = Gtk.CellRendererText()
        column_locale = Gtk.TreeViewColumn("", renderer_text, text=1)
        column_locale.set_sort_column_id(1)
        column_locale.set_resizable(False)
        column_locale.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        tree_view.append_column(column_locale)

        # Render a column for the category name
        renderer_text = Gtk.CellRendererText()
        column_category = Gtk.TreeViewColumn(_("Category"), renderer_text, text=2)
        column_category.set_sort_column_id(2)
        column_category.set_resizable(True)
        column_category.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        tree_view.append_column(column_category)

        # Render a column for the website URL
        renderer_link = Gtk.CellRendererText()
        column_link = Gtk.TreeViewColumn(_("Website URL"), renderer_link, text=3)
        column_link.set_sort_column_id(3)
        column_link.set_resizable(True)
        column_link.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        tree_view.append_column(column_link)

        return tree_view

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

        list(map(self.add_option, self.opts))

    def save_options(self):
        self.__enabled_files = self.opts[0].get_selected()
        self.config.set("websearch.enabled_files", self.__enabled_files)
        middle_name_handling = self.opts[1].get_value()
        self.config.set("websearch.middle_name_handling", middle_name_handling)
        self.config.save()

    def save_update_options(self, obj):
        self.save_options()
        self.update()

    def on_load(self):
        self.__enabled_files = self.config.get("websearch.enabled_files") or []
