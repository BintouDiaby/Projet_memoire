from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Utilisateur


class UtilisateurCreationForm(UserCreationForm):
    """Formulaire d'inscription : capture rôle + téléphone en plus des champs standards."""

    ROLE_CHOICES_PUBLIQUES = [
        (Utilisateur.Role.PROPRIETAIRE, 'Propriétaire'),
        (Utilisateur.Role.LOCATAIRE, 'Locataire'),
        (Utilisateur.Role.GESTIONNAIRE, 'Gestionnaire'),
    ]

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'votre.email@exemple.com', 'autocomplete': 'email'}),
    )
    telephone = forms.CharField(
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': '+225 07 00 00 00 00', 'autocomplete': 'tel'}),
        help_text="Utilisé pour les notifications de paiement (SMS).",
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES_PUBLIQUES,
        widget=forms.RadioSelect,
        initial=Utilisateur.Role.LOCATAIRE,
        label="Je suis",
    )

    class Meta:
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'telephone', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('username', 'first_name', 'last_name', 'password1', 'password2'):
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault('autocomplete', name.replace('1', '').replace('2', ''))

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet email.")
        return email

    def clean_telephone(self):
        tel = self.cleaned_data['telephone'].strip()
        digits = ''.join(c for c in tel if c.isdigit())
        if len(digits) < 8:
            raise forms.ValidationError("Numéro de téléphone invalide.")
        return tel

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.telephone = self.cleaned_data['telephone']
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user


class ConnexionForm(AuthenticationForm):
    """Login Django standard + case d'option `remember_me`."""

    remember_me = forms.BooleanField(required=False, initial=True, label="Se souvenir de moi")

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': "Nom d'utilisateur",
            'autocomplete': 'username',
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': 'Mot de passe',
            'autocomplete': 'current-password',
        })