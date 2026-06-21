import os
import sys
import django
import time

# Ajouter le répertoire parent (projet) au PYTHONPATH
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'immobilier_config.settings')
django.setup()

from django.conf import settings
from django.test import Client

# S'assurer que testserver est autorisé
if 'testserver' not in settings.ALLOWED_HOSTS:
    try:
        settings.ALLOWED_HOSTS += ['testserver']
    except Exception:
        pass

c = Client()
print('GET', c.get('/accounts/signup/company/').status_code)
uname = 'ci_test_' + str(int(time.time()))
data = {
    'username': uname,
    'first_name': 'CI',
    'last_name': 'Test',
    'email': uname + '@example.com',
    'telephone': '+2250700000000',
    'password1': 'Password123!',
    'password2': 'Password123!',
    'company_name': 'CI Company',
    'types': 'location_maison,vente_maison'
}
resp = c.post('/accounts/signup/company/', data, follow=True)
print('POST status', resp.status_code)
print('Final path', resp.request.get('PATH_INFO'))
print('Redirect chain', resp.redirect_chain)
html = resp.content.decode('utf-8')
# rechercher listes d'erreurs de formulaire
import re
errs = re.findall(r'<ul class="errorlist">(.*?)</ul>', html, re.S)
print('errorlist_count', len(errs))
for e in errs:
    text = re.sub(r'<[^>]+>', ' ', e)
    text = re.sub(r'\s+', ' ', text).strip()
    print('ERR:', text[:400])

# Aussi lister messages Django contrib
msgs = re.findall(r'<li class="messagelist.+?">(.*?)</li>', html, re.S)
print('messages_count', len(msgs))
for m in msgs:
    print('MSG:', re.sub(r'<[^>]+>', '', m).strip())

# Vérifier les erreurs du formulaire côté serveur (Utilisateurs form)
from utilisateurs.forms import UtilisateurCreationForm
form = UtilisateurCreationForm(data)
print('form.is_valid()', form.is_valid())
print('form.errors:', form.errors.as_json())
