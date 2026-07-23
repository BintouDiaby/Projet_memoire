"""API REST de la messagerie (app mobile, auth JWT).

Miroir des vues web de `views.py`, mais en JSON via DRF. Les permissions sont
portees par le queryset : on ne voit/ouvre que ses propres conversations
(demandeur, ou proprietaire dans la meme entreprise), les supprimees de son
cote etant exclues.
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from dashboard.services import NotificationService
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer, MessageSerializer, MessageCreateSerializer,
)


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    """list / retrieve des conversations de l'utilisateur, + actions messages,
    archiver, supprimer, et creation (nouvelle)."""
    serializer_class = ConversationSerializer

    def get_queryset(self):
        user = self.request.user
        qs = (
            Conversation.objects
            .filter(Q(demandeur=user) | Q(proprietaire__in=user.comptes_entreprise()))
            .select_related('bien', 'demandeur', 'proprietaire')
            .order_by('-mis_a_jour_le')
        )
        # Exclure les conversations supprimees du cote de cet utilisateur.
        gardees = [c.id for c in qs if not c.est_supprime_pour(user)]
        return qs.filter(id__in=gardees)

    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        """GET : liste les messages (et les marque lus). POST : envoie un message."""
        conv = self.get_object()

        if request.method == 'POST':
            entree = MessageCreateSerializer(data=request.data)
            entree.is_valid(raise_exception=True)
            msg = Message.objects.create(
                conversation=conv, expediteur=request.user,
                contenu=entree.validated_data['contenu'],
            )
            conv.mis_a_jour_le = timezone.now()
            conv.save(update_fields=['mis_a_jour_le'])
            destinataire = conv.proprietaire if request.user == conv.demandeur else conv.demandeur
            NotificationService.send(
                destinataire=destinataire, expediteur=request.user,
                type_notification='message',
                titre=f"Nouveau message de {request.user.get_full_name() or request.user.username}",
                message=msg.contenu[:120], lien=f'/chat/{conv.id}/',
            )
            return Response(
                MessageSerializer(msg, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )

        conv.messages.filter(lu=False).exclude(expediteur=request.user).update(lu=True)
        msgs = conv.messages.select_related('expediteur').all()
        return Response(MessageSerializer(msgs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def archiver(self, request, pk=None):
        """Bascule l'archivage de la conversation pour l'utilisateur courant."""
        conv = self.get_object()
        valeur = not conv.est_archive_pour(request.user)
        conv.archiver_pour(request.user, valeur)
        return Response({'archive': valeur})

    @action(detail=True, methods=['post'])
    def supprimer(self, request, pk=None):
        """Supprime la conversation du cote de l'utilisateur (l'autre la garde)."""
        conv = self.get_object()
        conv.supprimer_pour(request.user)
        return Response({'ok': True})

    @action(detail=False, methods=['post'])
    def nouvelle(self, request):
        """Demarre (ou rouvre) une conversation. Corps : {bien_id} OU {company_id}."""
        user = request.user
        bien_id = request.data.get('bien_id')
        company_id = request.data.get('company_id')

        if bien_id:
            from biens.models import Bien
            bien = get_object_or_404(Bien, id=bien_id)
            if user.meme_entreprise(bien.proprietaire):
                return Response(
                    {'detail': "Vous etes le proprietaire de ce bien."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            conv, _ = Conversation.objects.get_or_create(
                bien=bien, demandeur=user, defaults={'proprietaire': bien.proprietaire},
            )
        elif company_id:
            from utilisateurs.models import Company
            company = get_object_or_404(Company, id=company_id)
            if user.company_id == company.id:
                return Response(
                    {'detail': "Vous ne pouvez pas contacter votre propre entreprise."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            contact = company.users.filter(role='proprietaire').first() or company.users.first()
            if not contact:
                return Response(
                    {'detail': "Cette entreprise n'a aucun contact joignable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            conv, _ = Conversation.objects.get_or_create(
                bien=None, projet=None, demandeur=user, proprietaire=contact,
            )
        else:
            return Response(
                {'detail': "Fournir bien_id ou company_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # L'utilisateur est ici le demandeur : s'il avait supprime/archive cette
        # conversation, la rouvrir de son cote pour qu'elle reapparaisse.
        if conv.supprime_demandeur or conv.archive_demandeur:
            conv.supprime_demandeur = False
            conv.archive_demandeur = False
            conv.save(update_fields=['supprime_demandeur', 'archive_demandeur'])

        return Response(
            ConversationSerializer(conv, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
