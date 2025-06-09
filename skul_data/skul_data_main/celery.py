import os
from celery import Celery
from django.conf import settings

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "skul_data.skul_data_main.settings"
)  # Change based on the environment

app = Celery("skul_data")

# Load task modules from all registered Django app configs.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Explicitly tell Celery where to find tasks
app.autodiscover_tasks(
    [
        "skul_data.reports",
        "skul_data.analytics",
    ]
)
