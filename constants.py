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
    FAMILIES = "Families"

class PersonDataKeys(Enum):
    GIVEN = "given"
    MIDDLE = "middle"
    SURNAME = "surname"
    BIRTH_YEAR = "birth_year"
    BIRTH_YEAR_FROM = "birth_year_from"
    BIRTH_YEAR_TO = "birth_year_to"
    BIRTH_YEAR_BEFORE = "birth_year_before"
    BIRTH_YEAR_AFTER = "birth_year_after"
    DEATH_YEAR = "death_year"
    DEATH_YEAR_FROM = "death_year_from"
    DEATH_YEAR_TO = "death_year_to"
    DEATH_YEAR_BEFORE = "death_year_before"
    DEATH_YEAR_AFTER = "death_year_after"
    BIRTH_PLACE = "birth_place"
    DEATH_PLACE = "death_place"
    BIRTH_ROOT_PLACE = "birth_root_place"
    DEATH_ROOT_PLACE = "death_root_place"

class FamilyDataKeys(Enum):
    FATHER_GIVEN = "father_given"
    FATHER_MIDDLE = "father_middle"
    FATHER_SURNAME = "father_surname"
    FATHER_BIRTH_YEAR = "father_birth_year"
    FATHER_BIRTH_YEAR_FROM = "father_birth_year_from"
    FATHER_BIRTH_YEAR_TO = "father_birth_year_to"
    FATHER_BIRTH_YEAR_BEFORE = "father_birth_year_before"
    FATHER_BIRTH_YEAR_AFTER = "father_birth_year_after"
    FATHER_DEATH_YEAR = "father_death_year"
    FATHER_DEATH_YEAR_FROM = "father_death_year_from"
    FATHER_DEATH_YEAR_TO = "father_death_year_to"
    FATHER_DEATH_YEAR_BEFORE = "father_death_year_before"
    FATHER_DEATH_YEAR_AFTER = "father_death_year_after"
    FATHER_BIRTH_PLACE = "father_birth_place"
    FATHER_BIRTH_ROOT_PLACE = "father_birth_root_place"
    FATHER_DEATH_PLACE = "father_death_place"
    FATHER_DEATH_ROOT_PLACE = "father_death_root_place"

    MOTHER_GIVEN = "mother_given"
    MOTHER_MIDDLE = "mother_middle"
    MOTHER_SURNAME = "mother_surname"
    MOTHER_BIRTH_YEAR = "mother_birth_year"
    MOTHER_BIRTH_YEAR_FROM = "mother_birth_year_from"
    MOTHER_BIRTH_YEAR_TO = "mother_birth_year_to"
    MOTHER_BIRTH_YEAR_BEFORE = "mother_birth_year_before"
    MOTHER_BIRTH_YEAR_AFTER = "mother_birth_year_after"
    MOTHER_DEATH_YEAR = "mother_death_year"
    MOTHER_DEATH_YEAR_FROM = "mother_death_year_from"
    MOTHER_DEATH_YEAR_TO = "mother_death_year_to"
    MOTHER_DEATH_YEAR_BEFORE = "mother_death_year_before"
    MOTHER_DEATH_YEAR_AFTER = "mother_death_year_after"
    MOTHER_BIRTH_PLACE = "mother_birth_place"
    MOTHER_BIRTH_ROOT_PLACE = "mother_birth_root_place"
    MOTHER_DEATH_PLACE = "mother_death_place"
    MOTHER_DEATH_ROOT_PLACE = "mother_death_root_place"

    MARRIAGE_YEAR = "marriage_year"
    MARRIAGE_YEAR_FROM = "marriage_year_from"
    MARRIAGE_YEAR_TO = "marriage_year_to"
    MARRIAGE_YEAR_BEFORE = "marriage_year_before"
    MARRIAGE_YEAR_AFTER = "marriage_year_after"
    MARRIAGE_PLACE = "marriage_place"
    MARRIAGE_ROOT_PLACE = "marriage_root_place"

    DIVORCE_YEAR = "divorce_year"
    DIVORCE_YEAR_FROM = "divorce_year_from"
    DIVORCE_YEAR_TO = "divorce_year_to"
    DIVORCE_YEAR_BEFORE = "divorce_year_before"
    DIVORCE_YEAR_AFTER = "divorce_year_after"
    DIVORCE_PLACE = "divorce_place"
    DIVORCE_ROOT_PLACE = "divorce_root_place"

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

VISITED_HASH_FILE_PATH = os.path.join(os.path.dirname(__file__), "data", "visited_links.txt")
ICON_VISITED_PATH = os.path.join(os.path.dirname(__file__), "assets", "icons", "emblem-default.png")
SAVED_HASH_FILE_PATH = os.path.join(os.path.dirname(__file__), "data", "saved_links.txt")
ICON_SAVED_PATH = os.path.join(os.path.dirname(__file__), "assets", "icons", "media-floppy.png")
SKIPPED_DOMAIN_SUGGESTIONS_FILE_PATH = os.path.join(os.path.dirname(__file__), "data", "skipped_domain_suggestions.txt")

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
