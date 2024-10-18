"""
### FrontendConfigq
"""
from django.apps import AppConfig


class FrontendConfig(AppConfig):
    """
    FrontendConfig is a Django application configuration class for the 'frontend' app.

    Attributes:
        default_auto_field (str): Specifies the type of auto-incrementing 
        primary key to use for models in this app.
        name (str): The name of the app this configuration applies to.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'frontend'
