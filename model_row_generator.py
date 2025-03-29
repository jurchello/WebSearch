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
This module provides the ModelRowGenerator class, responsible for generating
data rows for the GTK ListStore model in the WebSearch Gramplet.

The class utilizes website data and common entity data to produce structured
rows that include icons, formatted URLs, and metadata necessary for display.
"""

import os
import json
import re
import sys
import traceback
from gi.repository import GdkPixbuf

from helpers import is_true
from constants import (
    DEFAULT_CATEGORY_ICON,
    CATEGORY_ICON,
    HIDDEN_HASH_FILE_PATH,
    SourceTypes,
    ICON_EARTH_PATH,
    ICON_PIN_PATH,
    ICON_CROSS_PATH,
    ICON_UID_PATH,
    ICON_CHAIN_PATH,
    ICON_USER_DATA_PATH,
    ICON_VISITED_PATH,
    ICON_SAVED_PATH,
    FLAGS_DIR,
    UID_ICON_WIDTH,
    UID_ICON_HEIGHT,
    ICON_SIZE,
    SOURCE_TYPE_SORT_ORDER,
    VISITED_HASH_FILE_PATH,
    SAVED_HASH_FILE_PATH,
    DEFAULT_SHOW_USER_DATA_ICON,
    DEFAULT_SHOW_FLAG_ICONS,
)

class ModelRowGenerator:
    """
    A utility class to generate formatted rows for the WebSearch Gramplet's ListStore model.

    This class processes website and entity data to generate structured rows,
    including formatted URLs, icons, and metadata for proper display.
    """
    def __init__(self, deps):
        """Initializes the ModelRowGenerator with required dependencies."""
        self.website_loader = deps.website_loader
        self.url_formatter = deps.url_formatter
        self.attribute_loader = deps.attribute_loader
        self.config_ini_manager = deps.config_ini_manager

    def generate(self, common_data, website_data):
        """Generates a structured data row for the ListStore model."""
        try:
            core_keys, attribute_keys, nav_type, obj = common_data
            nav, locale, title, is_enabled, url_pattern, comment, is_custom = website_data

            if nav != nav_type or not is_true(is_enabled):
                return None

            obj_handle = obj.get_handle()
            if self.should_be_hidden_link(url_pattern, nav_type, obj_handle):
                return None

            if locale in [SourceTypes.STATIC.value, SourceTypes.ATTR.value]:
                final_url = formatted_url = url_pattern
                pattern_keys_info, pattern_keys_json, replaced_keys_count, total_keys_count = self.get_empty_keys()
            else:
                combined_keys, matched_attribute_keys, pattern_keys_info, pattern_keys_json = self.prepare_data_keys(
                    core_keys, attribute_keys, url_pattern
                )

                final_url, formatted_url = self.prepare_urls(url_pattern, combined_keys, pattern_keys_info)

                locale, should_skip = self.evaluate_uid_locale(locale, pattern_keys_info, matched_attribute_keys)
                if should_skip:
                    return None

            icon_name = CATEGORY_ICON.get(nav_type, DEFAULT_CATEGORY_ICON)
            hash_value = self.website_loader.generate_hash(f"{final_url}|{obj_handle}")
            visited_icon, visited_icon_visible = self.get_visited_icon_data(hash_value)
            saved_icon, saved_icon_visible = self.get_saved_icon_data(hash_value)
            user_data_icon, user_data_icon_visible = (self.get_user_data_icon_data(is_custom))
            locale_icon, locale_icon_visible = self.get_locale_icon_data(locale)
            replaced_keys_count = len(pattern_keys_info["replaced_keys"])
            total_keys_count = self.get_total_keys_count(pattern_keys_info)
            keys_color = self.get_keys_color(replaced_keys_count, total_keys_count)
            locale_text = self.get_locale_text(locale)
            display_keys_count = self.get_display_keys_count(locale)
            source_type_sort = self.get_source_type_sort(locale)

            return {
                "icon_name": icon_name,
                "locale_text": locale_text,
                "title": title,
                "final_url": final_url,
                "comment": comment,
                "url_pattern": url_pattern,
                "keys_json": pattern_keys_json,
                "formatted_url": formatted_url,
                "visited_icon": visited_icon,
                "saved_icon": saved_icon,
                "nav_type": nav_type,
                "visited_icon_visible": visited_icon_visible,
                "saved_icon_visible": saved_icon_visible,
                "obj_handle": obj_handle,
                "replaced_keys_count": replaced_keys_count,
                "total_keys_count": total_keys_count,
                "keys_color": keys_color,
                "user_data_icon": user_data_icon,
                "user_data_icon_visible": user_data_icon_visible,
                "locale_icon": locale_icon,
                "locale_icon_visible": locale_icon_visible,
                "locale_text_visible": not locale_icon_visible,
                "display_keys_count": display_keys_count,
                "source_type_sort": source_type_sort,
            }
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

    def should_be_hidden_link(self, url_pattern, nav_type, obj_handle):
        """Determine if a link should be skipped based on hidden hash entries."""
        return (
            self.website_loader.has_string_in_file(f"{url_pattern}|{obj_handle}|{nav_type}", HIDDEN_HASH_FILE_PATH)
            or self.website_loader.has_string_in_file(f"{url_pattern}|{nav_type}", HIDDEN_HASH_FILE_PATH)
        )

    def prepare_data_keys(self, core_keys, attribute_keys, url_pattern):
        """
        Combines core entity keys with matched attribute keys relevant to the URL pattern.
        """
        matched_attribute_keys = self.attribute_loader.add_matching_keys_to_data(
            attribute_keys, url_pattern
        )
        combined_keys = core_keys.copy()
        combined_keys.update(matched_attribute_keys)
        pattern_keys_info = self.url_formatter.check_pattern_keys(url_pattern, combined_keys)
        pattern_keys_json = json.dumps(pattern_keys_info)
        return combined_keys, matched_attribute_keys, pattern_keys_info, pattern_keys_json

    def prepare_urls(self, url_pattern, combined_keys, keys):
        """Generate final and formatted URLs using combined keys and pattern keys info."""
        final_url = self.safe_percent_format(url_pattern, combined_keys)
        formatted_url = self.url_formatter.format(final_url, keys)
        return final_url, formatted_url

    def evaluate_uid_locale(self, locale, keys, matched_attribute_keys):
        """Check if the locale should be changed to UID and whether the link should be skipped."""
        should_skip = False
        final_locale = locale
        try:
            replaced_vars_set = {
                list(var.keys())[0] for var in keys["replaced_keys"]
            }
            if any(var in replaced_vars_set for var in matched_attribute_keys.keys()):
                final_locale = SourceTypes.UID.value
            if final_locale == SourceTypes.UID.value and not replaced_vars_set:
                should_skip = True
        except Exception:
            pass

        return final_locale, should_skip

    def get_empty_keys(self):
        """Return an empty pattern keys dictionary, its JSON, and zero counts."""
        keys = {
            "replaced_keys": [],
            "not_found_keys": [],
            "empty_keys": [],
        }
        return keys, json.dumps(keys), 0, 0

    def get_display_keys_count(self, locale):
        """Return False if key count display is not needed for this locale type."""
        display_keys_count = True
        if locale in [SourceTypes.STATIC.value, SourceTypes.ATTR.value]:
            display_keys_count = False
        return display_keys_count

    def get_total_keys_count(self, pattern_keys_info):
        """Calculate total number of keys from pattern keys info."""
        return (
            len(pattern_keys_info["not_found_keys"])
            + len(pattern_keys_info["replaced_keys"])
            + len(pattern_keys_info["empty_keys"])
        )

    def get_locale_text(self, locale):
        """Return locale text unless it is a special source type (like UID or STATIC)."""
        locale_text = locale
        if locale_text in [SourceTypes.COMMON.value, SourceTypes.UID.value, SourceTypes.STATIC.value, SourceTypes.CROSS.value, SourceTypes.ATTR.value]:
            locale_text = ""
        return locale_text

    def get_keys_color(self, replaced_keys_count, total_keys_count):
        """Determine color based on how many variables were replaced in the URL."""
        keys_color = "black"
        if replaced_keys_count == total_keys_count:
            keys_color = "green"
        elif replaced_keys_count not in (total_keys_count, 0):
            keys_color = "orange"
        elif replaced_keys_count == 0:
            keys_color = "red"
        return keys_color

    def get_source_type_sort(self, locale):
        """Return sorting key for the locale based on predefined source type order."""
        return SOURCE_TYPE_SORT_ORDER.get(locale, locale)

    def safe_percent_format(self, template: str, data: dict) -> str:
        """
        Safely replaces %(key)s-style placeholders in the template with values from data.
        Leaves unknown keys untouched and prevents TypeError.
        """
        def replacer(match):
            key = match.group(1)
            return str(data.get(key, f"%({key})s"))

        try:
            pattern = re.compile(r"%\((\w+)\)s")
            return pattern.sub(replacer, template)
        except Exception as e:
            print(f"❌ URL formatting error: {e}\nTemplate: {template}\nData: {data}", file=sys.stderr)
            return template

    def get_locale_icon_data(self, locale):
        """Returns an appropriate flag or icon based on the locale identifier."""
        locale_icon = None
        locale_icon_visible = False

        special_icons = {
            SourceTypes.COMMON.value: (ICON_EARTH_PATH, ICON_SIZE, ICON_SIZE),
            SourceTypes.STATIC.value: (ICON_PIN_PATH, ICON_SIZE, ICON_SIZE),
            SourceTypes.CROSS.value: (ICON_CROSS_PATH, ICON_SIZE, ICON_SIZE),
            SourceTypes.UID.value: (ICON_UID_PATH, UID_ICON_WIDTH, UID_ICON_HEIGHT),
            SourceTypes.ATTR.value: (ICON_CHAIN_PATH, ICON_SIZE, ICON_SIZE),
        }

        if locale in special_icons:
            path, width, height = special_icons[locale]
            return self.load_icon(path, width, height, label=locale)

        if not locale or not self.show_flag_icons():
            return None, False

        locale = locale.lower()
        flag_filename = f"{locale}.png"
        flag_path = os.path.join(FLAGS_DIR, flag_filename)
        if os.path.exists(flag_path):
            return self.load_icon(flag_path, ICON_SIZE, ICON_SIZE, label=locale)

        return None, False

    def load_icon(self, path, width, height, label=""):
        """Try to load and resize an icon. Returns (pixbuf, visible)."""
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)
            return pixbuf, True
        except Exception as e:
            print(f"❌ Error loading icon '{path}' {f'for {label}' if label else ''}: {e}", file=sys.stderr)
            return None, False

    def get_user_data_icon_data(self, is_custom):
        """Returns the user data icon if the entry is from a user-defined source."""
        user_data_icon = None
        user_data_icon_visible = False

        if not self.show_user_data_icons():
            return user_data_icon, user_data_icon_visible

        if is_custom:
            try:
                user_data_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_USER_DATA_PATH, ICON_SIZE, ICON_SIZE
                )
                user_data_icon_visible = True
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return user_data_icon, user_data_icon_visible

    def get_visited_icon_data(self, hash_value):
        """Returns the visited icon if the URL hash exists in the visited list."""
        visited_icon = None
        visited_icon_visible = False
        if self.website_loader.has_hash_in_file(hash_value, VISITED_HASH_FILE_PATH):
            try:
                visited_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_VISITED_PATH, ICON_SIZE, ICON_SIZE
                )
                visited_icon_visible = True
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return visited_icon, visited_icon_visible

    def get_saved_icon_data(self, hash_value):
        """Returns the saved icon if the URL hash exists in the saved list."""
        saved_icon = None
        saved_icon_visible = False
        if self.website_loader.has_hash_in_file(hash_value, SAVED_HASH_FILE_PATH):
            try:
                saved_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_SAVED_PATH, ICON_SIZE, ICON_SIZE
                )
                saved_icon_visible = True
            except Exception as e:
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return saved_icon, saved_icon_visible

    def show_flag_icons(self):
        """Returns the current state of the flag icons setting."""
        return self.config_ini_manager.get_boolean_option(
            "websearch.show_flag_icons", DEFAULT_SHOW_FLAG_ICONS
        )

    def show_user_data_icons(self):
        """Returns the current state of the user data icon setting."""
        return self.config_ini_manager.get_boolean_option(
            "websearch.show_user_data_icon", DEFAULT_SHOW_USER_DATA_ICON
        )