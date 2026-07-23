"""Routes de l'API REST de la messagerie, montees sous /api/messagerie/.

Separe de urls.py (qui sert l'interface web /chat/ en templates), pour ne pas
melanger l'UI et l'API JSON.
"""
from rest_framework.routers import SimpleRouter

from .api import ConversationViewSet

app_name = 'messagerie_api'

router = SimpleRouter()
router.register(r'conversations', ConversationViewSet, basename='api-conversation')

urlpatterns = router.urls
