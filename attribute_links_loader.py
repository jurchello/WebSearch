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

"""Extracts web links from attributes of Gramps objects for the WebSearch Gramplet."""

import re

from gramps.gen.lib import AttributeType
from gramps.gen.lib.srcattrtype import SrcAttributeType

from constants import URL_REGEX, URL_RSTRIP, SourceTypes


class AttributeLinksLoader:
    """
    Extracts direct URLs from the attributes of a Gramps object.

    This class scans all attributes of a given Gramps object (Person, Source, etc.),
    checks for any attribute that contains a valid URL, and returns a list of links
    that can be used by the WebSearch Gramplet or other components.
    """

    def __init__(self):
        """Initialize the regular expression for detecting URLs in attribute values."""
        self.url_regex = re.compile(URL_REGEX)

    def get_links_from_attributes(self, obj, nav_type):
        """Extract links from attributes of a given Gramps object."""
        links = []

        if not hasattr(obj, "get_attribute_list"):
            return links

        for attr in obj.get_attribute_list():
            attr_type = attr.get_type()

            if isinstance(attr_type, AttributeType):
                attr_name = attr_type.type2base()
            elif isinstance(attr_type, SrcAttributeType):
                attr_name = attr_type.string
            else:
                continue

            attr_value = attr.get_value()
            if not isinstance(attr_value, str):
                continue

            url = self._extract_url(attr_value)
            if url:
                url = url.rstrip(URL_RSTRIP)
                title = attr_name.strip()
                comment = None
                is_enabled = True
                is_custom = False
                links.append(
                    (
                        nav_type,
                        SourceTypes.ATTRIBUTE.value,
                        title,
                        is_enabled,
                        url,
                        comment,
                        is_custom,
                    )
                )

        return links

    def _extract_url(self, text):
        """Extract the first URL found in the given text."""
        match = self.url_regex.search(text)
        return match.group(0) if match else None
