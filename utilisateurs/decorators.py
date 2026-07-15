from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def acces_requis(*flags):
    """Décorateur de vue : bloque l'accès si l'utilisateur (employé) n'a
    aucun des flags de permission requis. Le Directeur (role=proprietaire)
    et le staff plateforme passent toujours. À poser après @login_required."""
    def decorateur(vue):
        @wraps(vue)
        def wrapper(request, *args, **kwargs):
            if not request.user.a_acces(*flags):
                messages.error(request, "Vous n'avez pas accès à cette page.")
                return redirect('dashboard_company')
            return vue(request, *args, **kwargs)
        return wrapper
    return decorateur
