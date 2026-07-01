"""
OrdenTec - PerfilMiddleware
Con django-tenants el schema ya aísla los datos.
Este middleware agrega el perfil y rol del usuario al request.
Bloquea el acceso si el usuario autenticado no pertenece a este taller.
"""
from django.db import connection
from django.shortcuts import redirect
from django.contrib.auth import logout

URLS_SIN_PERFIL = [
    '/login/', '/logout/', '/admin/', '/auth/token/',
    '/seguimiento/', '/invitacion/', '/registro/',
]

class PerfilMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.perfil = None
        request.rol    = None

        es_schema_tenant = (
            hasattr(connection, 'schema_name') and
            connection.schema_name != 'public'
        )

        if request.user.is_authenticated and es_schema_tenant:
            try:
                from taller.models import PerfilUsuario
                perfil = PerfilUsuario.objects.get(usuario=request.user, activo=True)
                request.perfil = perfil
                request.rol    = perfil.rol
            except PerfilUsuario.DoesNotExist:
                # El usuario es valido globalmente, pero NO pertenece a este taller.
                # Cerrar la sesion de este schema y mandarlo al login.
                if not any(request.path.startswith(u) for u in URLS_SIN_PERFIL):
                    logout(request)
                    return redirect('login')

        return self.get_response(request)