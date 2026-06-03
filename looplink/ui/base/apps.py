from django.apps import AppConfig


class BaseUIConfig(AppConfig):
    name = "looplink.ui.base"
    verbose_name = "Looplink Base UI Components"

    def ready(self):
        pass
