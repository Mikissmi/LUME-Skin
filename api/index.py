import os

# O projeto Django se chama "configuracao", não "LUMESkin".
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "configuracao.settings")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
