import re

class AttributeLinksLoader:
    """
    Extracts direct URLs from the attributes of a Gramps object.
    """

    def __init__(self):
        self.url_regex = re.compile(
            r"https?://[^\s]+"
        )

    def get_links_from_attributes(self, obj, nav_type):
        links = []

        if not hasattr(obj, "get_attribute_list"):
            return links

        for attr in obj.get_attribute_list():
            attr_name = attr.get_type().type2base()
            attr_value = attr.get_value()

            if not isinstance(attr_value, str):
                continue

            url = self._extract_url(attr_value)
            if url:
                title = attr_name.strip()
                comment = None
                is_enabled = True
                is_custom = True
                links.append((
                    nav_type,
                    "ATTR",
                    title,
                    is_enabled,
                    url,
                    comment,
                    is_custom
                ))

        return links

    def _extract_url(self, text):
        match = self.url_regex.search(text)
        return match.group(0) if match else None
