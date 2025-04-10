# ----------------------------------------------------------------------------
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
# ----------------------------------------------------------------------------


"""
This module provides a base class for generating AI prompt messages related to
genealogy website suggestions.
"""


class BasePromptBuilder:
    """Base class for building AI prompt messages for genealogy website suggestions."""

    def get_system_message(self) -> str:
        """Returns the system message to guide the AI's behavior."""
        return (
            "You assist in finding resources for genealogical research. "
            "Your response must be strictly formatted as a JSON array of objects "
            "with only two keys: 'domain' and 'url'. Do not include any additional text, "
            "explanations, or comments."
        )

    def get_user_message(self, locales, include_global, excluded_domains) -> str:
        """Generate the user message for the AI model."""
        if not locales:
            locale_text = "only globally used"
            locales_str = "none"
        else:
            locale_text = "both regional and globally used" if include_global else "regional"
            locales_str = ", ".join(locales)

        excluded_domains_str = ", ".join(excluded_domains) if excluded_domains else "none"

        return (
            f"I am looking for additional genealogical research websites for {locale_text} "
            f"resources. Relevant locales: {locales_str}. "
            f"Exclude the following domains: {excluded_domains_str}. "
            "Provide exactly 10 relevant websites formatted as a JSON array of objects "
            "with keys 'domain' and 'url'. "
            "Example response: [{'domain': 'example.com', 'url': 'https://example.com'}]. "
            "If no relevant websites are found, return an empty array [] without any explanations."
        )

    def build_prompt(self, locales, include_global, excluded_domains):
        """Build the full prompt tuple for the AI request."""
        return (
            self.get_system_message(),
            self.get_user_message(locales, include_global, excluded_domains),
        )
