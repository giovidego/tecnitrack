"""
TecniTrack - SuscripcionMiddleware
Verifica que el tenant tenga suscripcion activa.
Con schema-based tenancy, la Suscripcion vive en el schema del taller.
"""
from django.shortcuts import redirect
from django.db import connection

URLS_LIBRES = ['/login/', '/logout/', '/admin/', '/registro/', '/invitacion/',
               '/seguimiento/', '/planes/', '/suscripcion/']


class SuscripcionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Solo verificar en schemas de tenant
        if (request.user.is_authenticated and
                hasattr(connection, 'schema_name') and
                connection.schema_name != 'public'):

            path = request.path
            if not any(path.startswith(u) for u in URLS_LIBRES):
                self._verificar_suscripcion(request)

        return self.get_response(request)

    def _verificar_suscripcion(self, request):
        try:
            from taller.models import Suscripcion
            sus = Suscripcion.objects.first()
            if sus:
                request.suscripcion = sus
                if not sus.acceso_permitido:
                    if request.path != '/suscripcion/vencida/':
                        return redirect('suscripcion_vencida')
                if sus.estado == 'trial' and sus.dias_trial_restantes <= 7:
                    request.session['trial_dias_restantes'] = sus.dias_trial_restantes
                else:
                    request.session.pop('trial_dias_restantes', None)
        except Exception:
            pass
