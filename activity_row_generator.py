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
ActivityRowGenerator module for WebSearch Gramplet.

This module provides a class to transform raw activity log records stored in a file-based
database into structured, display-ready rows for a Gtk TreeView. It formats activity types,
timestamps, and additional metadata fields (such as links, file paths, domains, etc.) into a
concise and human-readable format.

Key features:
- Supports up to 1000 most recent activity entries.
- Provides localization for known activity types using gettext.
- Formats ISO timestamps using the shared utility function `format_iso_datetime`.
- Builds details string based on optional fields in the activity record.
"""


import os
import sys

from gettext import gettext as _
from helpers import format_iso_datetime
from constants import ActivityType


class ActivityRowGenerator:
    """
    A utility class to generate structured rows for the Activity Log ListStore model.

    This class processes activity log entries and returns data rows for display in the tree view.
    """

    def __init__(self, activities_model):
        """Initialize the ActivityRowGenerator with the activities DB model."""
        self.activities_model = activities_model

    def generate_rows(self):
        """
        Generates up to 1000 recent activity rows.
        Each row contains: activity_type, created_at, and a details string.
        """
        records = self.activities_model.order_by("id", reverse=True)[:1000]
        rows = []

        for record in records:
            try:
                activity_type = (
                    self.get_activity_label(record.get("activity_type", "")) + "   "
                )
                raw_date = record.get("created_at", "")
                created_at = format_iso_datetime(raw_date) + "   " if raw_date else ""
                details = self.build_details(record)

                row = {
                    "activity_type": activity_type,
                    "created_at": created_at,
                    "details": details,
                }
                rows.append(row)
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error generating activity row: {e}", file=sys.stderr)

        return rows

    def _format_activity_type(self, activity_type: str) -> str:
        """Convert snake_case activity type to title case."""
        return activity_type.replace("_", " ").title()

    def build_details(self, record):
        """
        Constructs a human-readable details string by joining available fields.
        """
        parts = []

        if "link" in record:
            parts.append(f"Link: {record['link']}")
        if "url_pattern" in record:
            parts.append(f"Pattern: {record['url_pattern']}")
        if "domain" in record:
            parts.append(f"Domain: {record['domain']}")
        if "file_path" in record:
            parts.append(f"File: {os.path.basename(record['file_path'])}")
        if "obj_gramps_id" in record:
            parts.append(f"Gramps ID: {record['obj_gramps_id']}")

        return " | ".join(parts)

    def get_activity_label(self, activity_type: str) -> str:
        """Return a localized, human-readable label for the given activity type."""
        labels = {
            ActivityType.LINK_VISIT.value: _("Link visited"),
            ActivityType.LINK_SAVE_TO_NOTE.value: _("Link saved to Note"),
            ActivityType.LINK_SAVE_TO_ATTRIBUTE.value: _("Link saved to Attribute"),
            ActivityType.PLACE_HISTORY_LOAD.value: _("Place history loaded"),
            ActivityType.DOMAIN_SKIP.value: _("Domain skipped"),
            ActivityType.HIDE_LINK_FOR_OBJECT.value: _("Link hidden for object"),
            ActivityType.HIDE_LINK_FOR_ALL.value: _("Link hidden for all objects"),
        }
        return labels.get(activity_type, "")
