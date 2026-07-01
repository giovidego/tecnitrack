"""
OrdenTec - Views de Suscripcion (schema-based tenancy)
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import connection


@login_required
def suscripcion_vencida(request):
    try:
        from .models import Suscripcion
        suscripcion = Suscripcion.objects.first()
    except Exception:
        suscripcion = None
    return render(request, 'suscripcion/vencida.html', {
        'taller':       connection.tenant,
        'suscripcion':  suscripcion,
        'planes':       settings.PLANES,
    })


@login_required
def ver_planes(request):
    try:
        from .models import Suscripcion
        suscripcion = Suscripcion.objects.first()
    except Exception:
        suscripcion = None
    return render(request, 'suscripcion/planes.html', {
        'taller':      connection.tenant,
        'suscripcion': suscripcion,
        'planes':      settings.PLANES,
        'rol':         getattr(request, 'rol', None),
    })
