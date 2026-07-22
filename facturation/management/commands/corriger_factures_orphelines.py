from django.core.management.base import BaseCommand
from django.utils import timezone

from contrats.models import Paiement
from facturation.tasks import generer_facture_pour_paiement


class Command(BaseCommand):
    help = (
        "Crée la Facture manquante pour tout Paiement passé ou du mois en cours "
        "qui n'en a pas encore (contrats signés en cours de mois avant le correctif "
        "de facturation/signals.py::creer_paiements_initiaux). Sans effet sur les "
        "Paiement qui ont déjà leur Facture — sûr à relancer plusieurs fois."
    )

    def handle(self, *args, **options):
        premier_jour_mois_courant = timezone.now().date().replace(day=1)
        corriges = 0

        paiements = (
            Paiement.objects.filter(mois__lte=premier_jour_mois_courant)
            .select_related('contrat', 'contrat__locataire')
        )
        for p in paiements:
            if hasattr(p, 'facture'):
                continue
            facture = generer_facture_pour_paiement(p, p.contrat)
            if facture:
                corriges += 1
                locataire = p.contrat.locataire.username if p.contrat.locataire else '—'
                self.stdout.write(
                    f"Facture créée : {facture.numero_facture} "
                    f"(paiement id={p.id}, contrat={p.contrat_id}, locataire={locataire}, mois={p.mois})"
                )

        self.stdout.write(self.style.SUCCESS(f"{corriges} facture(s) manquante(s) créée(s)."))
