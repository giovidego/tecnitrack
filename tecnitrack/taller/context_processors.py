"""
OrdenTec - Context processors
Expone info del tenant activo en todos los templates.
"""
from django.db import connection


def tenant_info(request):
    """
    Pone el taller activo (tenant) y el perfil del usuario en el contexto.
    connection.tenant es inyectado por django-tenants en cada request.
    """
    tenant = getattr(connection, 'tenant', None)
    return {
        'taller_actual': tenant,
        'taller_rol':    getattr(request, 'rol', None),
        'perfil_actual': getattr(request, 'perfil', None),
    }
