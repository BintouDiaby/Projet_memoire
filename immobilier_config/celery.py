import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'immobilier_config.settings')

app = Celery('immobilier_config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Configuration des tâches programmées
app.conf.beat_schedule = {
    'generer-factures-mensuelles': {
        'task': 'facturation.tasks.generer_factures_mensuelles',
        'schedule': crontab(hour=1, minute=0, day_of_month=1),  # 1h du matin le 1er
    },
    'envoyer-rappels-paiements': {
        'task': 'facturation.tasks.envoyer_rappels_paiements',
        'schedule': crontab(hour=8, minute=0),  # 8h du matin tous les jours
    },
    'mettre-a-jour-statut-paiements': {
        'task': 'contrats.tasks.mettre_a_jour_statut_paiements',
        'schedule': crontab(hour='*/6'),  # Toutes les 6 heures
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
