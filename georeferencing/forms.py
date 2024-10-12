from django import forms
import json

class PrettyJSONWidget(forms.Textarea):
    def format_value(self, value):
        """
        Format the value to be pretty-printed JSON.
        Handles cases where the value is None, an empty string, or invalid JSON.
        """
        if not value:  # Handle None or empty string values
            return ''
        try:
            if isinstance(value, (dict, list)):  # Handle dict or list types
                return json.dumps(value, indent=10)
            return json.dumps(json.loads(value), indent=4)  # Try to load and pretty-print JSON strings
        except (ValueError, TypeError):
            # In case value is not valid JSON, return the raw value or display an error message
            return value  # You can also raise an error or return a message if preferred