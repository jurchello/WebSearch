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

register(
    GRAMPLET,
    id="WebSearch",
    name=_("Web Search Gramplet"),
    description=_("Lists useful genealogy-related websites for research."),
    status=STABLE,
    version="0.11.7",
    fname="web_search.py",
    height=20,
    detached_width=400,
    detached_height=300,
    expand=True,
    gramplet="WebSearch",
    gramplet_title=_("Web Search"),
    gramps_target_version="5.2",
    navtypes=["Person", "Place", "Source", "Family"],
    include_in_listing=True,
)