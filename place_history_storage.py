import json
import os
import sys
from datetime import datetime
from constants import ADMINISTRATIVE_DIVISIONS_DIR

class PlaceHistoryStorage:
    """
    Class for handling the saving and loading of place history data to and from files.
    """

    @staticmethod
    def save_results_to_file(place_history_request_data, results):
        """
        Save the results to a JSON file in the ADMINISTRATIVE_DIVISIONS_DIR.
        The filename will be generated using place name and place handle.
        """
        # Ensure the directory exists
        if not os.path.exists(ADMINISTRATIVE_DIVISIONS_DIR):
            os.makedirs(ADMINISTRATIVE_DIVISIONS_DIR)

        # Generate a unique filename using place name and handle
        filename = f"ph_{place_history_request_data.gramps_id}_{place_history_request_data.handle}.json"
        file_path = os.path.join(ADMINISTRATIVE_DIVISIONS_DIR, filename)

        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(results, file, ensure_ascii=False, indent=4)
            print(f"Results saved to {file_path}")
        except Exception as e:
            print(f"❌ Error saving results to file: {e}", file=sys.stderr)

    @staticmethod
    def load_results_from_file(place_history_request_data):
        """
        Load the results from a JSON file in the ADMINISTRATIVE_DIVISIONS_DIR.
        Returns the data if the file exists, otherwise returns None.
        """
        filename = f"ph_{place_history_request_data.gramps_id}_{place_history_request_data.handle}.json"
        file_path = os.path.join(ADMINISTRATIVE_DIVISIONS_DIR, filename)

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    results = json.load(file)
                return results
            except Exception as e:
                print(f"❌ Error loading results from file: {e}", file=sys.stderr)
                return None
        return None
