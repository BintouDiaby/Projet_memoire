from django.test import TestCase, Client
from django.urls import reverse
from utilisateurs.models import Utilisateur
from .models import Bien


class BienFilterTests(TestCase):
    def setUp(self):
        self.client = Client()
        # propriétaires
        self.prop1 = Utilisateur.objects.create_user(username='p1', password='pass', role=Utilisateur.Role.PROPRIETAIRE)
        self.prop1.documents_verifies = True
        self.prop1.save()

        self.prop2 = Utilisateur.objects.create_user(username='p2', password='pass', role=Utilisateur.Role.PROPRIETAIRE)
        self.prop2.documents_verifies = False
        self.prop2.save()

        # biens
        Bien.objects.create(
            titre='Boutique à louer',
            description='Belle boutique',
            type_bien=Bien.TypeBien.BOUTIQUE,
            transaction_type=Bien.TransactionType.LOCATION,
            statut=Bien.Statut.DISPONIBLE,
            adresse='Rue 1', ville='Abidjan', code_postal='00000',
            surface_m2=50, nombre_chambres=0, nombre_salles_bain=1,
            nombre_etages=1, prix_mensuel=200000, photo_principale='none.jpg', proprietaire=self.prop1
        )

        Bien.objects.create(
            titre='Terrain à vendre',
            description='Grand terrain',
            type_bien=Bien.TypeBien.TERRAIN,
            transaction_type=Bien.TransactionType.VENTE,
            statut=Bien.Statut.DISPONIBLE,
            adresse='Zone 2', ville='Yamoussoukro', code_postal='11111',
            surface_m2=1000, nombre_chambres=0, nombre_salles_bain=0,
            nombre_etages=0, prix_mensuel=0, prix_vente=50000000, photo_principale='none.jpg', proprietaire=self.prop2
        )

    def test_filter_by_transaction_type(self):
        url = reverse('biens_ui:list')
        resp = self.client.get(url, {'transaction_type': Bien.TransactionType.VENTE})
        self.assertContains(resp, 'Terrain à vendre')
        self.assertNotContains(resp, 'Boutique à louer')

    def test_filter_by_type_bien(self):
        url = reverse('biens_ui:list')
        resp = self.client.get(url, {'type_bien': Bien.TypeBien.BOUTIQUE})
        self.assertContains(resp, 'Boutique à louer')
        self.assertNotContains(resp, 'Terrain à vendre')

    def test_filter_entreprises_verifiees(self):
        url = reverse('biens_ui:list')
        resp = self.client.get(url, {'entreprises_verifiees': '1'})
        self.assertContains(resp, 'Boutique à louer')
        self.assertNotContains(resp, 'Terrain à vendre')
