from django.test import Client, override_settings
from utilisateurs.models import Utilisateur
from biens.models import Bien, Visite, Reservation
from contrats.models import Contrat, Reclamation

fatimah = Utilisateur.objects.get(username='fatimahdby07')

with override_settings(ALLOWED_HOSTS=['testserver', '127.0.0.1', 'localhost']):
    c = Client()
    c.force_login(fatimah)

    for url in ['/biens/mes-visites/', '/biens/mes-reservations/', '/contrats/mes-reclamations/']:
        resp = c.get(url)
        print(url, '->', resp.status_code, len(resp.content), 'bytes')
        if resp.status_code != 200:
            print('  CONTENT:', resp.content[:500])

    print()
    print('Visites existantes pour fatimah:', Visite.objects.filter(locataire=fatimah).count())
    print('Reservations existantes pour fatimah:', Reservation.objects.filter(client=fatimah).count())
    print('Contrats existants pour fatimah:', Contrat.objects.filter(locataire=fatimah).count())
    print('Reclamations existantes pour fatimah:', Reclamation.objects.filter(locataire=fatimah).count() if hasattr(Reclamation, 'locataire') else 'N/A')

    # essayer de creer une reclamation sur un bien sans contrat
    bien_sans_contrat = Bien.objects.exclude(id__in=Contrat.objects.filter(locataire=fatimah).values_list('bien_id', flat=True)).first()
    if bien_sans_contrat:
        resp = c.post(f'/contrats/reclamation/{bien_sans_contrat.id}/', {'titre': 'test', 'description': 'test', 'categorie': 'autre'})
        print()
        print(f'POST reclamation sur bien {bien_sans_contrat.id} (sans contrat) -> status:', resp.status_code)

    # essayer de reserver un bien disponible
    bien_dispo = Bien.objects.filter(statut='disponible').exclude(proprietaire=fatimah).first()
    if bien_dispo:
        resp = c.post(f'/biens/reserver/{bien_dispo.id}/', {'notes': 'test reservation'})
        print(f'POST reserver bien {bien_dispo.id} -> status:', resp.status_code, '-> redirect:', resp.get('Location'))
        Reservation.objects.filter(bien=bien_dispo, client=fatimah).delete()
