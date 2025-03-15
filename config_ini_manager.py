import os
from gramps.gen.config import config as configman
from gramps.gen.const import GRAMPS_LOCALE as glocale
from constants import *

class ConfigINIManager:
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), "config")
        if not os.path.exists(self.config_file + ".ini"):
            open(self.config_file + ".ini", "w").close()

        self.config = configman.register_manager(self.config_file)
        self.config.register("websearch.enabled_files", DEFAULT_ENABLED_FILES)
        self.config.register("websearch.middle_name_handling", DEFAULT_MIDDLE_NAME_HANDLING)
        self.config.register("websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT)
        self.config.register("websearch.show_short_url", DEFAULT_SHOW_SHORT_URL)
        self.config.register("websearch.url_compactness_level", DEFAULT_URL_COMPACTNESS_LEVEL)
        self.config.register("websearch.use_openai", DEFAULT_USE_OPEN_AI)
        self.config.register("websearch.openai_api_key", "")
        self.config.load()

    def get_boolean_option(self, key, default=True):
        value = self.config.get(key)
        if value is None:
            return default
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)

    def get_enum(self, key, enum_class, default):
        value = self.config.get(key)
        return value if value in [e.value for e in enum_class] else default

    def get_string(self, key, default=""):
        return (self.config.get(key) or default).strip()

    def get_list(self, key, default=[]):
        value = self.config.get(key)
        if value is None:
            return default
        if not isinstance(value, list):
            return default
        return value

    def set_boolean_option(self, key, value):
        if isinstance(value, str):
            value = value.lower() == 'true'
        self.config.set(key, bool(value))

    def set_enum(self, key, value):
        self.config.set(key, value)

    def set_string(self, key, value):
        self.config.set(key, (value or "").strip())

    def save(self):
        self.config.save()

    def set_boolean_list(self, key, values):
        if isinstance(values, list):
            self.config.set(key, values)
        else:
            print(f"❌ ERROR: {key}: {type(values)}")

    def print_config(self):
        print("\n=== ConfigINIManager Settings ===")
        config_keys = [
            ("websearch.enabled_files", "🟢 Enable CSV Files"),
            ("websearch.middle_name_handling", "🔵 Middle Name Handling"),
            ("websearch.url_prefix_replacement", "🟠 URL Prefix Replacement"),
            ("websearch.show_short_url", "🟢 Show Shortened URL"),
            ("websearch.url_compactness_level", "🔵 URL Compactness Level"),
            ("websearch.use_openai", "🟢 Use OpenAI"),
            ("websearch.openai_api_key", "🟠 OpenAI API Key")
        ]
        for key, label in config_keys:
            value = self.config.get(key)
            if isinstance(value, list):
                print(f"{label}: {value if value else 'None'}")
            elif isinstance(value, bool) or key in ["websearch.show_short_url", "websearch.use_openai"]:
                print(f"{label}: {bool(value)}")
            elif isinstance(value, str):
                print(f"{label}: {value.strip() if value.strip() else 'None'}")
            else:
                print(f"{label}: {value}")
        print("========================\n")
