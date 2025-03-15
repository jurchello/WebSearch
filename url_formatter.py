import re
from constants import *

class UrlFormatter:
    def __init__(self, config_ini_manager):
        self.config_ini_manager = config_ini_manager
        self.init(self.config_ini_manager)

    def init(self, config_ini_manager):
        self.__show_short_url = config_ini_manager.get_boolean_option("websearch.show_short_url", DEFAULT_SHOW_SHORT_URL)
        self.__url_compactness_level = config_ini_manager.get_enum("websearch.url_compactness_level", URLCompactnessLevel, DEFAULT_URL_COMPACTNESS_LEVEL)
        self.__url_prefix_replacement = config_ini_manager.get_string("websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT)

    def format(self, url, variables):
        self.init(self.config_ini_manager)

        if not self.__show_short_url or not self.__url_compactness_level:
            return url

        if self.__url_compactness_level == URLCompactnessLevel.SHORTEST.value:
            return self.format_shortest(url)
        elif self.__url_compactness_level == URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value:
            return self.format_compact_no_attributes(url, variables)
        elif self.__url_compactness_level == URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value:
            return self.format_compact_with_attributes(url, variables)
        elif self.__url_compactness_level == URLCompactnessLevel.LONG.value:
            return self.format_long(url)

        return url

    def format_shortest(self, url):
        return self.remove_url_query_params(self.trim_url_prefix(url))

    def format_compact_no_attributes(self, url, variables):
        clean_url = self.remove_url_query_params(self.trim_url_prefix(url))
        return self.append_variables_to_url(clean_url, variables, False)

    def format_compact_with_attributes(self, url, variables):
        clean_url = self.remove_url_query_params(self.trim_url_prefix(url))
        return self.append_variables_to_url(clean_url, variables, True)

    def format_long(self, url):
        return self.trim_url_prefix(url)

    def trim_url_prefix(self, url):
        for prefix in URL_PREFIXES_TO_TRIM:
            if url.startswith(prefix):
                return self.__url_prefix_replacement + url[len(prefix):]
        return url

    def remove_url_query_params(self, url):
        return url.split('?')[0]

    def append_variables_to_url(self, url, variables, show_attribute):
        replaced_variables = variables.get('replaced_variables', [])
        if replaced_variables:
            formatted_vars = []
            for var in replaced_variables:
                for key, value in var.items():
                    formatted_vars.append(f"{key}={value}" if show_attribute else f"{value}")
            return url + DEFAULT_QUERY_PARAMETERS_REPLACEMENT + DEFAULT_QUERY_PARAMETERS_REPLACEMENT.join(formatted_vars)
        return url + DEFAULT_QUERY_PARAMETERS_REPLACEMENT

    def check_pattern_variables(self, url_pattern, data):
        pattern_variables = re.findall(r"%\((.*?)\)s", url_pattern)

        replaced_variables = []
        not_found_variables = []
        empty_variables = []

        for variable in pattern_variables:
            value = data.get(variable)
            if value is None:
                not_found_variables.append(variable)
            elif value == "":
                empty_variables.append(variable)
            else:
                replaced_variables.append({variable: value})

        return {
           "replaced_variables": replaced_variables,
           "not_found_variables": not_found_variables,
           "empty_variables": empty_variables,
       }