from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.urls import reverse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Utilisateur, ProprietaireProfile, LocataireProfile
from .serializers import (
    UtilisateurSerializer, UtilisateurCreationSerializer,
    ProprietaireProfileSerializer, LocataireProfileSerializer
)
from .forms import UtilisateurCreationForm, ConnexionForm


def ui_index(request):
    """Page front simple pour les utilisateurs"""
    context = {
        'title': 'Utilisateurs',
        'api_url': '/api/utilisateurs/'
    }
    return render(request, 'utilisateurs/index.html', context)


def ui_list(request):
    """Liste publique d'utilisateurs (propriétaires par exemple)"""
    users = Utilisateur.objects.filter(is_active=True).order_by('-date_joined')[:50]
    return render(request, 'utilisateurs/list.html', {'users': users, 'title': 'Utilisateurs'})


def ui_detail(request, pk):
    user = Utilisateur.objects.filter(id=pk).first()
    if not user:
        from django.http import Http404
        raise Http404('Utilisateur non trouvé')
    return render(request, 'utilisateurs/detail.html', {'user': user})


class UtilisateurViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des utilisateurs"""
    queryset = Utilisateur.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Choisir le serializer approprié selon l'action"""
        if self.action == 'create':
            return UtilisateurCreationSerializer
        return UtilisateurSerializer
    
    def get_permissions(self):
        """Modifier les permissions par action"""
        if self.action == 'create':
            return [AllowAny()]
        return super().get_permissions()

    
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Récupérer le profil de l'utilisateur connecté"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'post'])
    def dashboard_preferences(self, request):
        """Lire ou mettre à jour les préférences du dashboard de l'utilisateur connecté"""
        user = request.user
        if request.method == 'GET':
            return Response({'dashboard_preferences': user.dashboard_preferences})

        # POST -> mettre à jour
        prefs = request.data.get('dashboard_preferences')
        if prefs is None:
            return Response({'error': 'Aucune préférence fournie'}, status=status.HTTP_400_BAD_REQUEST)

        user.dashboard_preferences = prefs
        user.save()
        return Response({'success': True, 'dashboard_preferences': user.dashboard_preferences})
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Changer le mot de passe de l'utilisateur"""
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not user.check_password(old_password):
            return Response(
                {'error': 'Ancien mot de passe incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        return Response({'success': 'Mot de passe changé avec succès'})
    
    @action(detail=True, methods=['get'])
    def proprietaire_profile(self, request, pk=None):
        """Récupérer le profil propriétaire de l'utilisateur"""
        user = self.get_object()
        if user.role != 'proprietaire':
            return Response(
                {'error': "Cet utilisateur n'est pas un propriétaire"},
                status=status.HTTP_400_BAD_REQUEST
            )
        profile = user.proprietaire_profile
        serializer = ProprietaireProfileSerializer(profile)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def locataire_profile(self, request, pk=None):
        """Récupérer le profil locataire de l'utilisateur"""
        user = self.get_object()
        if user.role != 'locataire':
            return Response(
                {'error': "Cet utilisateur n'est pas un locataire"},
                status=status.HTTP_400_BAD_REQUEST
            )
        profile = user.locataire_profile
        serializer = LocataireProfileSerializer(profile)
        return Response(serializer.data)


class ProprietaireProfileViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des profils propriétaires"""
    queryset = ProprietaireProfile.objects.all()
    serializer_class = ProprietaireProfileSerializer
    permission_classes = [IsAuthenticated]


class LocataireProfileViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des profils locataires"""
    queryset = LocataireProfile.objects.all()
    serializer_class = LocataireProfileSerializer
    permission_classes = [IsAuthenticated]


def _public_landing_stats():
    """Stats publiques affichées sur les pages de login/signup pour donner du contexte."""
    from biens.models import Bien
    from contrats.models import Contrat

    return {
        'biens_total': Bien.objects.count(),
        'biens_disponibles': Bien.objects.filter(statut=Bien.Statut.DISPONIBLE).count(),
        'utilisateurs_actifs': Utilisateur.objects.filter(is_active=True).count(),
        'contrats_actifs': Contrat.objects.filter(statut=Contrat.Statut.EN_COURS).count(),
    }


def _redirect_apres_login(user):
    """Retourne la redirection appropriée selon le rôle de l'utilisateur."""
    role = getattr(user, 'role', None)

    # Locataire → espace client/marketplace
    if role == Utilisateur.Role.LOCATAIRE:
        return redirect('guest_landing')

    # Propriétaire / gestionnaire / admin → dashboard entreprise (toujours)
    # Le dashboard gère lui-même l'affichage de l'onboarding si la company est incomplète
    return redirect('dashboard_company')


def login_view(request):
    """Vue de connexion avec gestion du `remember_me` et redirection par rôle."""
    if request.user.is_authenticated:
        return _redirect_apres_login(request.user)

    form = ConnexionForm(request)
    if request.method == 'POST':
        form = ConnexionForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 jours

            return _redirect_apres_login(user)

    context = {
        'form': form,
        'next': request.GET.get('next', ''),
        'stats': _public_landing_stats(),
    }
    return render(request, 'registration/login.html', context)


def company_login(request):
    """Vue de connexion dédiée aux comptes entreprise (GET + POST autonome)."""
    if request.user.is_authenticated:
        return _redirect_apres_login(request.user)

    form = ConnexionForm(request)
    if request.method == 'POST':
        form = ConnexionForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)
            return _redirect_apres_login(user)

    context = {
        'form': form,
        'next': request.GET.get('next', '/dashboard/company/'),
        'stats': _public_landing_stats(),
    }
    return render(request, 'registration/login_company.html', context)


def _envoyer_email_confirmation(request, user):
    """Génère un code OTP à 6 chiffres, le sauvegarde (valide 10 minutes) et
    l'envoie par email. Un OTP saisi dans l'app fonctionne même si l'email est
    ouvert sur un autre réseau/appareil que celui du serveur — contrairement à
    un lien de confirmation, dont l'hôte dépend de la requête qui l'a généré
    et peut être inaccessible ailleurs. La vérification reste informative —
    elle ne bloque pas l'accès au compte."""
    import random
    from django.utils import timezone
    from django.core.mail import send_mail
    from django.template.loader import render_to_string

    if not user.email:
        return
    code = f"{random.randint(0, 999999):06d}"
    user.otp_code = code
    user.otp_expire_le = timezone.now() + timezone.timedelta(minutes=10)
    user.save(update_fields=['otp_code', 'otp_expire_le'])

    contenu = render_to_string('registration/email_confirmation.txt', {
        'user': user,
        'code': code,
    })
    try:
        send_mail(
            "Votre code de confirmation — ImmoGérer",
            contenu,
            None,
            [user.email],
            fail_silently=True,
        )
    except Exception:
        pass


@login_required
def confirmer_email(request):
    """Page de saisie du code OTP envoyé par email."""
    from django.utils import timezone

    erreur = None
    if request.method == 'POST':
        code_saisi = request.POST.get('code', '').strip()
        user = request.user
        if user.email_verifie:
            pass
        elif not user.otp_code or not user.otp_expire_le or timezone.now() > user.otp_expire_le:
            erreur = "Ce code a expiré. Demandez-en un nouveau."
        elif code_saisi != user.otp_code:
            erreur = "Code incorrect. Vérifiez et réessayez."
        else:
            user.email_verifie = True
            user.otp_code = ''
            user.otp_expire_le = None
            user.save(update_fields=['email_verifie', 'otp_code', 'otp_expire_le'])
            messages.success(request, "Adresse email confirmée !")
            return redirect(request.POST.get('next') or 'dashboard')

    return render(request, 'registration/email_confirmee.html', {'erreur': erreur})


@login_required
def renvoyer_confirmation(request):
    """Renvoie un nouveau code OTP à l'utilisateur connecté et l'amène sur la
    page de saisie du code."""
    if request.user.email_verifie:
        messages.info(request, "Votre adresse email est déjà confirmée.")
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'dashboard')
    _envoyer_email_confirmation(request, request.user)
    messages.success(request, f"Code de confirmation renvoyé à {request.user.email}.")
    return redirect('confirmer_email')


def logout_view(request):
    """Déconnexion : renvoie vers la page d'accueil publique avec confirmation."""
    logout(request)
    messages.success(request, "Vous avez été déconnecté(e) avec succès.")
    return redirect('landing')


def signup(request):
    """Inscription : crée l'utilisateur, son profil rôle-spécifique, et le connecte."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # Le template n'envoie pas le champ `role` — l'imposer en tant que proprietaire
        post = request.POST.copy()
        post.setdefault('role', Utilisateur.Role.PROPRIETAIRE)
        form = UtilisateurCreationForm(post)
        if form.is_valid():
            user = form.save()

            # Créer automatiquement le profil correspondant au rôle
            if user.role == Utilisateur.Role.PROPRIETAIRE:
                ProprietaireProfile.objects.get_or_create(utilisateur=user)
            elif user.role == Utilisateur.Role.LOCATAIRE:
                LocataireProfile.objects.get_or_create(utilisateur=user)

            login(request, user)
            _envoyer_email_confirmation(request, user)
            messages.success(request, f"Bienvenue {user.first_name or user.username} ! Votre compte a été créé.")

            # Si l'onboarding a fourni des `types` en GET (ex: ?types=location,vente),
            # les appliquer à la company de l'utilisateur.
            types_qs = request.GET.get('types')
            if types_qs:
                types_list = [t for t in types_qs.split(',') if t]
                if types_list:
                    from .models import Company
                    company = getattr(user, 'company', None)
                    if company is None:
                        company = Company.objects.create(name=f"{user.username} Company", types=types_list)
                        user.company = company
                    else:
                        current = list(company.types or [])
                        for t in types_list:
                            if t not in current:
                                current.append(t)
                        company.types = current
                        company.save()
                    user.save()

            return redirect('dashboard')
    else:
        form = UtilisateurCreationForm(initial={'role': request.GET.get('role', Utilisateur.Role.LOCATAIRE)})

    context = {
        'form': form,
        'stats': _public_landing_stats(),
        'role_descriptions': {
            Utilisateur.Role.PROPRIETAIRE: "Je mets en location ou en vente mes biens.",
            Utilisateur.Role.LOCATAIRE: "Je cherche un logement à louer.",
            Utilisateur.Role.GESTIONNAIRE: "Je gère un parc immobilier pour des propriétaires.",
        },
    }
    return render(request, 'registration/signup.html', context)


def company_signup(request):
    """Inscription simplifiée pour une entreprise : crée l'utilisateur + company + profil.

    Formulaire combiné (GET) et création (POST). Utilise `UtilisateurCreationForm`.
    Champs attendus POST : username, first_name, last_name, email, telephone,
    password1, password2, company_name, rccm, company_phone, company_adresse
    """
    from .forms import UtilisateurCreationForm
    from .models import Company, ProprietaireProfile

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        post = request.POST.copy()
        post.setdefault('role', Utilisateur.Role.PROPRIETAIRE)
        form = UtilisateurCreationForm(post)
        if form.is_valid():
            user = form.save()

            # créer Company minimal
            company_name = request.POST.get('company_name') or f"{user.username} Company"
            types_qs = request.POST.get('types', '')
            types_list = [t for t in types_qs.split(',') if t]
            company = Company.objects.create(name=company_name, types=types_list)
            user.company = company
            user.save()

            # profil propriétaire
            prof, _ = ProprietaireProfile.objects.get_or_create(utilisateur=user)
            prof.nom_entreprise = company_name
            prof.numero_siret_siren = request.POST.get('rccm') or prof.numero_siret_siren
            prof.save()

            # connecter l'utilisateur
            login(request, user)
            _envoyer_email_confirmation(request, user)
            messages.success(request, "Compte entreprise créé — configurez votre espace.")
            # Rediriger vers l'URL absolue pour éviter tout problème de reverse/name
            return redirect('/dashboard/company/')
        else:
            # Rendre visibles les erreurs du formulaire (le template est JS-driven)
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
    else:
        # préremplir le rôle en proprietaire
        form = UtilisateurCreationForm(initial={'role': Utilisateur.Role.PROPRIETAIRE})

    context = {'form': form, 'stats': _public_landing_stats()}
    return render(request, 'registration/company_signup.html', context)


def onboarding_apply(request):
    """Applique les types sélectionnés par l'onboarding.
    - Pour un propriétaire/gestionnaire déjà connecté : les activités choisies
      sont enregistrées (fusionnées) sur sa company, puis il est renvoyé vers
      son dashboard entreprise.
    - Pour les anonymes : on redirige vers la page d'inscription en pré-remplissant
      `types` et en forçant l'affichage (`force=1`).
    """
    types_qs = request.GET.get('types', '')
    types_list = [t for t in types_qs.split(',') if t]

    if request.user.is_authenticated:
        user = request.user
        if types_list and user.role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
            from .models import Company
            company = getattr(user, 'company', None)
            if company is None:
                company = Company.objects.create(name=f"{user.username} Company", types=types_list)
                user.company = company
                user.save()
            else:
                current = list(company.types or [])
                for t in types_list:
                    if t not in current:
                        current.append(t)
                company.types = current
                company.save()
            messages.success(request, "Vos activités ont été mises à jour.")
        return redirect('dashboard')

    # Utilisateur anonyme → renvoyer vers la page d'inscription en pré-remplissant
    # `types`. Si des `types` sont fournis, diriger vers la page `company_signup`
    # (flux entreprise). Sinon, utiliser l'inscription générique.
    from django.urls import reverse
    qs_parts = []
    if types_list:
        qs_parts.append('types=' + ','.join(types_list))
        return redirect(reverse('company_signup') + ('?' + '&'.join(qs_parts)))

    return redirect(reverse('signup') + ('?' + '&'.join(qs_parts) if qs_parts else ''))


@login_required
def company_profile_edit(request):
    """Formulaire simple permettant à l'entreprise de compléter son profil
    (logo, photo de couverture, coordonnées, description, RCCM)."""
    user = request.user
    if user.role not in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
        return redirect('dashboard')

    from .models import Company

    company = getattr(user, 'company', None)
    if company is None:
        company = Company.objects.create(name=user.get_full_name() or user.username)
        user.company = company
        user.save()

    prof, _ = ProprietaireProfile.objects.get_or_create(utilisateur=user)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            company.name = name
        company.description = request.POST.get('description', '').strip()
        company.adresse = request.POST.get('adresse', '').strip()
        company.ville = request.POST.get('ville', '').strip()
        company.telephone = request.POST.get('telephone', '').strip()
        company.email = request.POST.get('email', '').strip()
        if request.FILES.get('logo'):
            company.logo = request.FILES['logo']
        if request.FILES.get('cover_image'):
            company.cover_image = request.FILES['cover_image']
        company.save()

        rccm = request.POST.get('numero_siret_siren', '').strip()
        if rccm:
            prof.numero_siret_siren = rccm
        if not prof.nom_entreprise:
            prof.nom_entreprise = company.name
        prof.save()

        messages.success(request, "Profil entreprise mis à jour.")
        return redirect(request.POST.get('next') or 'dashboard_company')

    return render(request, 'dashboard/company_edit.html', {'company': company, 'prof': prof})


@login_required
def set_company_type(request, type_name):
    """Ajouter un type d'activité à la company de l'utilisateur (créée si absente)."""
    user = request.user
    # Créer une company minimale si nécessaire
    company = getattr(user, 'company', None)
    if company is None:
        from .models import Company
        company = Company.objects.create(name=f"{user.username} Company")
        user.company = company

    # Normaliser
    type_name = str(type_name)
    if type_name not in company.types:
        company.types.append(type_name)
        company.save()

    user.save()
    return redirect('dashboard')


@login_required
def set_company_types(request):
    """Recevoir une liste de types (POST) et les ajouter à la company de l'utilisateur."""
    if request.method != 'POST':
        return redirect('home')

    types = request.POST.getlist('types')
    if not types:
        from django.contrib import messages
        messages.error(request, "Sélectionnez au moins une activité.")
        return redirect('home')

    user = request.user
    company = getattr(user, 'company', None)
    if company is None:
        from .models import Company
        company = Company.objects.create(name=f"{user.username} Company")
        user.company = company

    # Normaliser et fusionner sans doublons
    current = list(company.types or [])
    for t in types:
        if t not in current:
            current.append(str(t))

    company.types = current
    company.save()
    user.save()
    return redirect('home')


def onboarding(request):
    """Afficher la page d'onboarding (sélection du rôle/interface).

    Cette page est publique : l'utilisateur choisit son rôle puis est
    redirigé vers l'inscription (`signup`) avec `?role=...` ou vers la page
    de connexion.
    """
    # Si l'utilisateur est connecté et doit configurer son espace (propriétaire/gestionnaire
    # sans company ou sans types), lui laisser accéder à la page d'onboarding.
    if request.user.is_authenticated:
        if request.user.role in (Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE):
            # Autoriser la configuration d'espace pour les utilisateurs entreprise
            return render(request, 'onboarding.html')
        # Les autres rôles n'ont pas à configurer l'onboarding
        return redirect('dashboard')

    # Utilisateur anonyme → afficher l'onboarding public
    return render(request, 'onboarding.html')


def choose_profile(request):
    """Page simple permettant de choisir d'abord le profil (Particulier / Entreprise)

    Elle redirige vers la page d'inscription en pré-sélectionnant le rôle.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    context = {
        'stats': _public_landing_stats(),
    }
    return render(request, 'choose_profile.html', context)


@login_required
def admin_verification_entreprises(request):
    """Écran admin : entreprises en attente de vérification (RCCM/documents).

    `documents_verifies` (Utilisateur, filtre la vitrine publique) et
    `certification` (ProprietaireProfile, pilote le badge « Vérifiée » du
    dashboard) sont deux champs distincts qui doivent rester synchronisés —
    jusqu'ici rien ne les modifiait en dehors de l'admin Django brut.
    """
    if not (request.user.is_staff or request.user.role == Utilisateur.Role.ADMIN):
        return HttpResponseForbidden("Réservé aux administrateurs.")

    entreprises = (
        Utilisateur.objects.filter(
            role__in=[Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE],
            documents_verifies=False,
        )
        .select_related('company', 'proprietaire_profile')
        .order_by('date_creation')
    )
    entreprises_verifiees = (
        Utilisateur.objects.filter(
            role__in=[Utilisateur.Role.PROPRIETAIRE, Utilisateur.Role.GESTIONNAIRE],
            documents_verifies=True,
        )
        .select_related('company', 'proprietaire_profile')
        .order_by('-date_creation')[:20]
    )
    return render(request, 'utilisateurs/admin_verification.html', {
        'entreprises': entreprises,
        'entreprises_verifiees': entreprises_verifiees,
    })


@login_required
def admin_verifier_entreprise(request, user_id):
    """Approuve ou rejette la vérification d'une entreprise (RCCM/documents)."""
    if not (request.user.is_staff or request.user.role == Utilisateur.Role.ADMIN):
        return HttpResponseForbidden("Réservé aux administrateurs.")
    if request.method != 'POST':
        return redirect('admin_verification_entreprises')

    from dashboard.services import NotificationService

    cible = Utilisateur.objects.filter(id=user_id).first()
    if not cible:
        messages.error(request, "Entreprise introuvable.")
        return redirect('admin_verification_entreprises')

    action = request.POST.get('action')
    if action == 'approuver':
        cible.documents_verifies = True
        cible.save(update_fields=['documents_verifies'])
        prof, _ = ProprietaireProfile.objects.get_or_create(utilisateur=cible)
        prof.certification = True
        prof.save(update_fields=['certification'])
        NotificationService.send(
            destinataire=cible, type_notification='systeme',
            titre="Votre entreprise est vérifiée",
            message="Vos documents ont été validés. Le badge « Entreprise vérifiée » est maintenant actif.",
            lien='/dashboard/company/',
        )
        messages.success(request, f"{cible.get_full_name() or cible.username} vérifiée avec succès.")
    elif action == 'rejeter':
        cible.documents_verifies = False
        cible.save(update_fields=['documents_verifies'])
        NotificationService.send(
            destinataire=cible, type_notification='systeme',
            titre="Vérification refusée",
            message="Vos documents n'ont pas pu être validés. Contactez le support pour plus d'informations.",
            lien='/dashboard/entreprise/modifier/',
        )
        messages.success(request, "Vérification refusée, l'entreprise a été notifiée.")

    return redirect('admin_verification_entreprises')
