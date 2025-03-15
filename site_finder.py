try:
    import openai
except ImportError:
    print("⚠ OpenAI module is missing. Install it using: `pip install openai`.", file=sys.stderr)

import json
import sys

class SiteFinder:
    """
    A class for retrieving genealogy-related websites using OpenAI.
    Attributes:
        api_key (str): API key for OpenAI authentication.
    Methods:
        find_sites(excluded_domains, locales, include_global):
            Sends a query to OpenAI and returns a list of genealogy research websites.
    """
    def __init__(self, api_key):
        self.api_key = api_key

    def find_sites(self, excluded_domains, locales, include_global):
        system_message = (
            "You assist in finding resources for genealogical research. "
            "Your response must be strictly formatted as a JSON array of objects with only two keys: 'domain' and 'url'. "
            "Do not include any additional text, explanations, or comments."
        )

        if not locales:
            locale_text = "only globally used"
            locales_str = "none"
        else:
            locale_text = "both regional and globally used" if include_global else "regional"
            locales_str = ", ".join(locales)

        excluded_domains_str = ", ".join(excluded_domains) if excluded_domains else "none"

        user_message = (
            f"I am looking for additional genealogical research websites for {locale_text} resources. "
            f"Relevant locales: {locales_str}. "
            f"Exclude the following domains: {excluded_domains_str}. "
            "Provide exactly 10 relevant websites formatted as a JSON array of objects with keys 'domain' and 'url'. "
            "Example response: [{'{\"domain\": \"example.com\", \"url\": \"https://example.com\"}'}]. "
            "If no relevant websites are found, return an empty array [] without any explanations."
        )

        try:
            client = openai.OpenAI(api_key=self.api_key)
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
            )
        except Exception as e:
            print(f"❌ Unexpected error while calling OpenAI: {e}", file=sys.stderr)
            return "[]"

        try:
            return completion.choices[0].message.content
        except Exception as e:
            print(f"❌ Error parsing OpenAI response: {e}", file=sys.stderr)
            return "[]"