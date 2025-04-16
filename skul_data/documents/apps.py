from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.documents"
    label = "documents"

    # def ready(self):
    #     """Automatically seed categories when Django starts"""
    #     try:
    #         seed_document_categories()
    #     except Exception as e:
    #         print(f"⚠️ Could not seed categories: {e}")
    def ready(self):
        pass
