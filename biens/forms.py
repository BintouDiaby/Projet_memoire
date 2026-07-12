from django import forms
from .models import Bien


class BienForm(forms.ModelForm):
    class Meta:
        model = Bien
        fields = [
            'titre', 'description', 'photo_principale',
            'type_bien', 'transaction_type', 'statut',
            'adresse', 'quartier', 'commune', 'ville', 'latitude', 'longitude',
            'surface_m2', 'nombre_chambres', 'nombre_salles_bain',
            'prix_mensuel', 'prix_vente', 'prix_depot_garantie',
        ]
        widgets = {
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'photo_principale': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'type_bien': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'quartier': forms.TextInput(attrs={'class': 'form-control'}),
            'commune': forms.TextInput(attrs={'class': 'form-control'}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ex: 5.3364'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ex: -4.0267'}),
            'surface_m2': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_chambres': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_salles_bain': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_mensuel': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_vente': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_depot_garantie': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le modèle ne déclare pas blank=True, mais une annonce existe très
        # bien sans photo (cf. les `{% if bien.photo_principale %}` dans les
        # templates) : ne pas forcer un nouvel upload à chaque modification.
        self.fields['photo_principale'].required = False
