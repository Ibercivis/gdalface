from django.apps import AppConfig


class UserProfileConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_profile'
    
    def ready(self):
        """
        Importar las señales cuando la aplicación está lista.
        """
        import user_profile.signals  # pylint: disable=unused-import,import-outside-toplevel
