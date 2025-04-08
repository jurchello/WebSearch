import re
import os


class GrampletVersionExtractor:
    """
    Extracts the version of the WebSearch Gramplet from the current directory.

    Usage:
        extractor = GrampletVersionExtractor()
        version = extractor.get_version()
        print(f"WebSearch Gramplet version: {version}")
    """

    def __init__(self):
        """
        Initializes the extractor with the default Gramplet file name.
        """
        self.file_name = "WebSearch.gpr.py"
        self.file_path = os.path.join(os.path.dirname(__file__), self.file_name)

    def get(self):
        """
        Extracts the version from the WebSearch Gramplet file.

        :return: Version string if found, otherwise "Version not found".
        """
        if not os.path.isfile(self.file_path):
            return f"File '{self.file_name}' not found in the current directory."

        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                content = file.read()

            match = re.search(r'version\s*=\s*"(.*?)"', content)
            if match:
                return match.group(1)
            return "Version not found"
        except Exception as e:
            return f"Error reading file: {e}"
