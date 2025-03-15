import os
from enum import Enum

# --------------------------
# ENUMS
# --------------------------

class MiddleNameHandling(Enum):
    LEAVE_ALONE = "leave alone"
    SEPARATE = "separate"
    REMOVE = "remove"

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

class CsvColumnNames(Enum):
    NAV_TYPE = "Navigation type"
    CATEGORY = "Category"
    IS_ENABLED = "Is enabled"
    URL = "URL"
    COMMENT = "Comment"

class URLCompactnessLevel(Enum):
    SHORTEST = "shortest"
    COMPACT_NO_ATTRIBUTES = "compact_no_attributes"
    COMPACT_WITH_ATTRIBUTES = "compact_with_attributes"
    LONG = "long"

class PlaceDataKeys(Enum):
    PLACE = "place"
    ROOT_PLACE = "root_place"

class SourceDataKeys(Enum):
    TITLE = "source_title"

# --------------------------
# CONSTANTS
# --------------------------

COMMON_LOCALE_SIGN = "★"
ICON_SIZE = 16
URL_PREFIXES_TO_TRIM = ["https://www.", "http://www.", "https://", "http://"]
COMMON_CSV_FILE_NAME = "common-links.csv"

VISITED_HASH_FILE_PATH = os.path.join(os.path.dirname(__file__), "visited_links.txt")
ICON_VISITED_PATH = os.path.join(os.path.dirname(__file__), "icons", "emblem-default.png")
SAVED_HASH_FILE_PATH = os.path.join(os.path.dirname(__file__), "saved_links.txt")
ICON_SAVED_PATH = os.path.join(os.path.dirname(__file__), "icons", "media-floppy.png")
SKIPPED_DOMAIN_SUGGESTIONS_FILE_PATH = os.path.join(os.path.dirname(__file__), "skipped_domain_suggestions.txt")

DEFAULT_CATEGORY_ICON = "gramps-gramplet"
DEFAULT_SHOW_SHORT_URL = True
DEFAULT_USE_OPEN_AI = False
DEFAULT_URL_PREFIX_REPLACEMENT = ""
DEFAULT_QUERY_PARAMETERS_REPLACEMENT = "..."
DEFAULT_URL_COMPACTNESS_LEVEL = URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value
DEFAULT_MIDDLE_NAME_HANDLING = MiddleNameHandling.SEPARATE.value
DEFAULT_ENABLED_FILES = [COMMON_CSV_FILE_NAME]

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
