import os
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'immobilier_config.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = 'admin'
email = 'admin@example.com'
password = 'adminpass123'
if User.objects.filter(username=username).exists():
    print('Superuser already exists')
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superuser created: username={username} password={password}')
