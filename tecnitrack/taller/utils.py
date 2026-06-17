"""
TecniTrack - Notificaciones automaticas (schema-based tenancy)
El taller activo se obtiene de connection.tenant en vez de orden.taller
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db import connection
import logging

logger = logging.getLogger(__name__)

MENSAJES_ESTADO = {
    'recibido':         {'asunto': 'Hemos recibido tu equipo - Orden {numero}',       'mensaje_corto': 'Tu equipo fue recibido en el taller.'},
    'diagnostico':      {'asunto': 'Tu equipo esta en diagnostico - Orden {numero}',  'mensaje_corto': 'Nuestro tecnico esta diagnosticando tu equipo.'},
    'espera_repuestos': {'asunto': 'Esperando repuestos - Orden {numero}',            'mensaje_corto': 'Tu equipo necesita repuestos. Te avisaremos cuando lleguen.'},
    'en_reparacion':    {'asunto': 'Tu equipo esta en reparacion - Orden {numero}',   'mensaje_corto': 'Ya comenzamos a reparar tu equipo.'},
    'listo':            {'asunto': 'Tu equipo esta listo para retirar - Orden {numero}', 'mensaje_corto': 'Tu equipo esta reparado y listo para retirar.'},
    'entregado':        {'asunto': 'Equipo entregado - Orden {numero}',               'mensaje_corto': 'Tu equipo fue entregado. Gracias por confiar en nosotros.'},
    'cancelado':        {'asunto': 'Orden cancelada - Orden {numero}',                'mensaje_corto': 'Tu orden de reparacion fue cancelada.'},
}


def enviar_notificacion(orden, estado, usuario=None):
    """
    Envia email al cliente cuando cambia el estado de la orden.
    Con schema-based tenancy, el taller activo se obtiene de connection.tenant.
    """
    taller = getattr(connection, 'tenant', None)
    if not taller or not taller.notif_email:
        return False
    if not orden.cliente.email:
        logger.warning(f"Orden {orden.numero}: cliente sin email.")
        return False

    info = MENSAJES_ESTADO.get(estado)
    if not info:
        return False

    asunto = info['asunto'].format(numero=orden.numero)
    ctx = {
        'orden':          orden,
        'taller':         taller,
        'mensaje_corto':  info['mensaje_corto'],
        'url_seguimiento': orden.get_url_seguimiento(),
        'estado_display': orden.get_estado_display(),
    }

    try:
        html = render_to_string('emails/notificacion_estado.html', ctx)
        txt  = render_to_string('emails/notificacion_estado.txt',  ctx)
        send_mail(
            subject=f"[{taller.nombre}] {asunto}",
            message=txt,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[orden.cliente.email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f"Notificacion enviada -> {orden.cliente.email} | Orden {orden.numero} | Estado: {estado}")
        return True
    except Exception as e:
        logger.error(f"Error enviando notificacion orden {orden.numero}: {e}")
        return False
