from rest_framework import serializers
from .models import Utilisateur, ProprietaireProfile, LocataireProfile
from django.contrib.auth.password_validation import validate_password


class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer pour l'utilisateur"""
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    dashboard_preferences = serializers.JSONField(required=False)
    
    class Meta:
        model = Utilisateur
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 
            'role_display', 'telephone', 'adresse', 'ville', 'code_postal', 
            'photo_profil', 'bio', 'email_verifie', 'documents_verifies',
            'dashboard_preferences',
            'date_creation', 'date_modification'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']


class UtilisateurCreationSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'utilisateur avec validation"""
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = Utilisateur
        fields = [
            'username', 'email', 'password', 'password2', 'first_name',
            'last_name', 'role', 'telephone', 'adresse', 'ville', 'code_postal'
        ]
    
    def validate_username(self, value):
        if Utilisateur.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur existe déjà.")
        return value
    
    def validate_email(self, value):
        if Utilisateur.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email existe déjà.")
        return value
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                'password': "Les mots de passe ne correspondent pas."
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        
        user = Utilisateur.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        # Créer les profils associés
        if user.role == 'proprietaire':
            ProprietaireProfile.objects.create(utilisateur=user)
        elif user.role == 'locataire':
            LocataireProfile.objects.create(utilisateur=user)
        
        return user


class ProprietaireProfileSerializer(serializers.ModelSerializer):
    """Serializer pour le profil propriétaire"""
    utilisateur = UtilisateurSerializer(read_only=True)
    utilisateur_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Utilisateur.objects.filter(role='proprietaire')
    )
    
    class Meta:
        model = ProprietaireProfile
        fields = [
            'id', 'utilisateur', 'utilisateur_id', 'numero_siret_siren',
            'nom_entreprise', 'numero_licence', 'iban', 'nombre_proprietes',
            'experience_annees', 'certification'
        ]
        read_only_fields = ['id']


class LocataireProfileSerializer(serializers.ModelSerializer):
    """Serializer pour le profil locataire"""
    utilisateur = UtilisateurSerializer(read_only=True)
    utilisateur_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=Utilisateur.objects.filter(role='locataire')
    )
    
    class Meta:
        model = LocataireProfile
        fields = [
            'id', 'utilisateur', 'utilisateur_id', 'numero_identite',
            'revenu_mensuel', 'numero_reference_bancaire', 'avis_impot',
            'preuve_emploi', 'garant_contact', 'localisation_preferee',
            'budget_max_mensuel'
        ]
        read_only_fields = ['id']
