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
from gramps.gen.lib import AttributeType, Note
from gramps.gui.editors import EditObject

from constants import (
    SourceTypes,
    URL_REGEX,
    URL_RSTRIP,
)


class NoteLinksLoader:

    def __init__(self, db):
        self.db = db
        self.url_regex = re.compile(URL_REGEX)

    def get_links_from_notes(self, obj, nav_type):
        """Main method to get links from notes."""
        links = []
        if hasattr(obj, "get_note_list"):
            note_handles = obj.get_note_list()
            for note_handle in note_handles:
                note_obj = self.get_note_object(note_handle)
                if note_obj:
                    links.extend(self.get_links_from_note_obj(note_obj, nav_type))
        elif isinstance(obj, Note):
            links.extend(self.get_links_from_note_obj(obj, nav_type))

        return links

    def get_links_from_note_obj(self, note_obj, nav_type):
        """Extract links from a single note object."""
        links = []
        parsed_links = self.parse_links_from_text(note_obj.get())
        existing_links = self.get_existing_links(note_obj)

        # Add parsed links if not in existing links
        for url in parsed_links:
            if url not in existing_links:
                links.append(self.format_parsed_link(nav_type, url))
                existing_links.add(url)

        # Add existing note links
        note_links = note_obj.get_links()
        for link in note_links:
            formatted_link = self.format_existing_link(nav_type, link)
            if formatted_link:
                links.append(formatted_link)

        return links

    def get_note_object(self, note_handle):
        """Retrieve the note object from the database."""
        try:
            note_obj = self.db.get_note_from_handle(note_handle)
            if note_obj is None:
                print(f"⚠️ Warning: Note with handle {note_handle} not found.")
            return note_obj
        except Exception:
            print(f"⚠️ Warning: Handle {note_handle} not found in the database.")
            return None

    def parse_links_from_text(self, note_text):
        """Extract URLs from the note text."""
        urls = self.url_regex.findall(note_text)
        return list(set(url.rstrip(URL_RSTRIP) for url in urls))

    def get_existing_links(self, note_obj):
        """Extract existing links from a note object."""
        existing_links = set()
        note_links = note_obj.get_links()
        for link in note_links:
            if len(link) == 4:
                source, obj_type, sub_type, handle = link
                if source != 'gramps':
                    existing_links.add(handle.rstrip(URL_RSTRIP))
        return existing_links

    def format_parsed_link(self, nav_type, url):
        """Format a parsed link into the required structure."""
        return (
            nav_type,
            "NOTE",
            "None Link (parsed)",
            True,
            url,
            "",
            False
        )

    def format_existing_link(self, nav_type, link):
        """Format an existing note link into the required structure."""
        if len(link) != 4:
            print(f"⚠️ Warning: Invalid link format: {link}")
            return None

        source, obj_type, sub_type, handle = link
        if not (source and obj_type and sub_type and handle):
            return None

        if source == 'gramps':
            final_url = f"{source}://{obj_type}/{sub_type}/{handle}"
            title = 'Note Link (internal)'
        else:
            final_url = handle
            title = 'Note Link (external)'

        return (
            nav_type,
            "NOTE",
            title,
            True,
            final_url,
            "",
            False
        )