from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from contrats.models import Contrat
from biens.models import Bien


class HomeLocataireTests(TestCase):
	def setUp(self):
		User = get_user_model()
		self.client = Client()
		# créer un utilisateur locataire
		self.user = User.objects.create_user(username='toto', password='pass', role='locataire')

	def test_home_shows_recommendations_for_new_locataire(self):
		self.client.login(username='toto', password='pass')
		resp = self.client.get(reverse('dashboard'))
		self.assertEqual(resp.status_code, 200)
		# nouveau locataire : doit fournir la clé locataire_is_new
		self.assertIn('locataire_is_new', resp.context)
