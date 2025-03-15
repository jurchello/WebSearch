from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug.menu import BooleanListOption, EnumeratedListOption, StringOption
from constants import *
from website_loader import WebsiteLoader

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

class SettingsUIManager:
    def __init__(self, config_ini_manager):
        self.config_ini_manager = config_ini_manager
        self.opts = []

    def build_options(self):
        self.opts.clear()
        self.add_csv_files_option()
        self.add_enum_option(
            "websearch.middle_name_handling",
            "Middle Name Handling",
            MiddleNameHandling,
            DEFAULT_MIDDLE_NAME_HANDLING,
            descriptions={
                MiddleNameHandling.LEAVE_ALONE.value: _("Leave alone"),
                MiddleNameHandling.SEPARATE.value: _("Separate"),
                MiddleNameHandling.REMOVE.value: _("Remove"),
            }
        )
        self.add_boolean_option("websearch.show_short_url", "Show Shortened URL", DEFAULT_SHOW_SHORT_URL)
        self.add_enum_option(
            "websearch.url_compactness_level",
            "URL Compactness Level",
            URLCompactnessLevel,
            DEFAULT_URL_COMPACTNESS_LEVEL,
            descriptions={
                URLCompactnessLevel.SHORTEST.value: _("Shortest - No Prefix, No Variables"),
                URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value: _("Compact - No Prefix, Variables Without Attributes (Default)"),
                URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value: _("Compact - No Prefix, Variables With Attributes"),
                URLCompactnessLevel.LONG.value: _("Long - Without Prefix on the Left"),
            }
        )
        self.add_string_option("websearch.url_prefix_replacement", "URL Prefix Replacement", DEFAULT_URL_PREFIX_REPLACEMENT)
        self.add_boolean_option("websearch.use_openai", "Use OpenAI", DEFAULT_USE_OPEN_AI)
        self.add_string_option("websearch.openai_api_key", "OpenAI API Key")

        return self.opts

    def add_csv_files_option(self):
        all_files, selected_files = WebsiteLoader.get_all_and_selected_files(self.config_ini_manager)

        print(f"All CSV Files: {all_files}")
        print(f"Selected CSV Files: {selected_files}")

        opt = BooleanListOption("Enable CSV Files")
        for file in all_files:
            opt.add_button(file, file in selected_files)
        self.opts.append(opt)

    def add_boolean_option(self, config_key, label, default):
        opt = BooleanListOption(label)
        value = self.config_ini_manager.get_boolean_option(config_key, default)
        opt.add_button(label, value)
        self.opts.append(opt)

    def add_enum_option(self, config_key, label, enum_class, default, descriptions=None):
        opt = EnumeratedListOption(label, default)
        for item in enum_class:
            display_text = descriptions.get(item.value, item.value) if descriptions else item.value
            opt.add_item(item.value, _(display_text))
        opt.set_value(self.config_ini_manager.get_enum(config_key, enum_class, default))
        self.opts.append(opt)

    def add_string_option(self, config_key, label, default=""):
        value = self.config_ini_manager.get_string(config_key, default)
        opt = StringOption(label, value)
        self.opts.append(opt)

    def print_settings(self):
        print("\n=== SettingsUIManager Settings ===")
        for opt in self.opts:
            option_name = opt.get_label()
            if isinstance(opt, BooleanListOption):
                selected = opt.get_selected()
                if len(selected) > 1:
                    print(f"🟢 {option_name}: {selected}")
                else:
                    print(f"🟢 {option_name}: {bool(selected)}")
            elif isinstance(opt, EnumeratedListOption):
                current_value = opt.get_value()
                print(f"🔵 {option_name}: {current_value}")
            elif isinstance(opt, StringOption):
                current_value = opt.get_value()
                print(f"🟠 {option_name}: {current_value}")
        print("========================\n")