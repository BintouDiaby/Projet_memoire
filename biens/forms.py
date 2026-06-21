from django import forms
from .models import Bien


class BienForm(forms.ModelForm):
    class Meta:
        model = Bien
        fields = [
            'titre', 'description', 'adresse', 'ville', 'type_bien',
            'transaction_type', 'nombre_chambres', 'prix_mensuel', 'statut'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
