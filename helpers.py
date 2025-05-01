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
Utility functions for use across Gramplet modules.

Includes:
- Boolean string parsing (`is_true`)
- Retrieval of system locale from GRAMPS_LOCALE
"""

from datetime import datetime

from gramps.gen.const import GRAMPS_LOCALE as glocale


def is_true(value: str) -> bool:
    """
    Checks whether a given string value represents a boolean 'true'.

    Accepts common variants like "1", "true", "yes", "y".
    """
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def get_system_locale() -> str:
    """
    Extracts the system locale string from the GRAMPS_LOCALE object.
    """
    return (
        glocale.language[0] if isinstance(glocale.language, list) else glocale.language
    )


def format_iso_datetime(iso_string: str) -> str:
    """Format ISO 8601 datetime string to a more readable format."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ""
