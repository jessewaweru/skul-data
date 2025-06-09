"""
WSGI config for skul_data project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

# import os

# from django.core.wsgi import get_wsgi_application

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "skul_data_main.settings.production")

# application = get_wsgi_application()


import os
from django.core.wsgi import get_wsgi_application
import sys
from pathlib import Path

# Add the project directory to the PYTHONPATH
project_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(project_dir))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "skul_data.skul_main_data.settings.production"
)

application = get_wsgi_application()
