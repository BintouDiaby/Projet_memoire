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
username = 'Admin'
email = 'admin@example.com'
password = 'admin123'
qs = User.objects.filter(username__iexact=username)
if qs.exists():
    deleted_count, _ = qs.delete()
    print(f'Deleted {deleted_count} existing user(s) matching {username} (case-insensitive)')
else:
    print('No existing user to delete')
User.objects.create_superuser(username=username, email=email, password=password)
print(f'Created superuser: username={username} password={password}')
