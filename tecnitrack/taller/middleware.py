"""
TecniTrack - PerfilMiddleware
Con django-tenants el schema ya aísla los datos.
Este middleware agrega el perfil y rol del usuario al request.
"""
from django.db import connection


class PerfilMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.perfil = None
        request.rol    = None

        if (request.user.is_authenticated and
                hasattr(connection, 'schema_name') and
                connection.schema_name != 'public'):
            try:
                from taller.models import PerfilUsuario
                perfil = PerfilUsuario.objects.get(usuario=request.user, activo=True)
                request.perfil = perfil
                request.rol    = perfil.rol
            except Exception:
                pass

        return self.get_response(request)
