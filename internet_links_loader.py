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

import re
from gramps.gen.lib.srcattrtype import SrcAttributeType
from gramps.gen.lib import AttributeType

from constants import SourceTypes


class InternetLinksLoader:

    def __init__(self):
        """Initialize the regular expression for detecting URLs in attribute values."""
        self.url_regex = re.compile(r"https?://[^\s]+")

    def get_links_from_internet_objects(self, person, nav_type):

        links = []
        list = person.get_url_list()

        for url_obj in list:
            description = url_obj.get_description()
            full_path = url_obj.get_full_path()
            urlType = url_obj.get_type()
            if urlType:
                type = urlType.xml_str()

            url = self._extract_url(full_path)

            if type:
                title = type
            else:
                title = "No title"

            if url:
                title = title.strip()
                comment = description
                is_enabled = True
                is_custom = True
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
        """Extract the first URL found in the given text."""
        match = self.url_regex.search(text)
        return match.group(0) if match else None
