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

"""Extracts and formats links from the 'Internet' tab of Gramps objects."""


import re

from constants import URL_REGEX, URL_RSTRIP, SourceTypes


class InternetLinksLoader:
    """Loader for extracting and formatting URLs from the 'Internet' tab."""

    def __init__(self):
        """Compiles the regular expression for URL detection."""
        self.url_regex = re.compile(URL_REGEX)

    def get_links_from_internet_objects(self, obj, nav_type):
        """Extracts formatted URLs from an object's 'Internet' tab."""
        links = []
        url_list = obj.get_url_list()

        for url_obj in url_list:
            description = url_obj.get_description()
            full_path = url_obj.get_full_path()
            url_type = url_obj.get_type()
            if url_type:
                url_type_str = url_type.xml_str()

            url = self._extract_url(full_path)

            if url_type_str:
                title = url_type_str
            else:
                title = "No title"

            if url:
                url = url.rstrip(URL_RSTRIP)
                title = title.strip()
                comment = description
                is_enabled = True
                is_custom = False
                links.append(
                    (
                        nav_type,
                        SourceTypes.INTERNET.value,
                        title,
                        is_enabled,
                        url,
                        comment,
                        is_custom,
                    )
                )

        return links

    def _extract_url(self, text):
        """Extracts the first URL found in the given text."""
        match = self.url_regex.search(text)
        return match.group(0) if match else None
