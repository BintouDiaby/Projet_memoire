"""Package init: tenter d'initialiser Celery si disponible.

Certaines environnements de test n'ont pas `celery` installé. On protège
l'import pour éviter d'échouer l'initialisation de Django.
"""
try:
	from .celery import app as celery_app
except Exception:
	celery_app = None

__all__ = ('celery_app',)
