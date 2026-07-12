from django import forms
from .models import Contrat, Reclamation


class ContratCreationForm(forms.ModelForm):
    """Formulaire de création d'un contrat par le propriétaire.

    `bien` et `locataire` sont restreints dans la vue (via `queryset`) à ce
    qui appartient/concerne réellement le propriétaire connecté.
    """

    class Meta:
        model = Contrat
        fields = [
            'bien', 'locataire', 'date_debut', 'date_fin',
            'prix_mensuel', 'prix_depot_garantie', 'charges_mensuelles',
            'nombre_mois_minimum', 'jour_paiement', 'conditions_speciales',
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'conditions_speciales': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        date_debut = cleaned.get('date_debut')
        date_fin = cleaned.get('date_fin')
        if date_debut and date_fin and date_fin <= date_debut:
            raise forms.ValidationError("La date de fin doit être après la date de début.")
        return cleaned


class ReclamationForm(forms.ModelForm):
    """Formulaire de signalement d'un problème par le locataire sur un bien
    qu'il loue (ou a loué). `bien` et `locataire` sont fixés dans la vue."""

    class Meta:
        model = Reclamation
        fields = ['titre', 'priorite', 'description']
        widgets = {
            'titre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Ex : Fuite d'eau dans la salle de bain"}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': "Décrivez le problème rencontré…"}),
        }
