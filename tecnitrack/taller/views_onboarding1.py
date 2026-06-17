"""
TecniTrack - Views de Onboarding (schema-based tenancy)
El registro de nuevos talleres crea un schema de PostgreSQL via django-tenants.
"""
import secrets
from django.core.cache import cache

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db import connection

from tenants.models import Taller, Dominio
from .forms_onboarding import (
    RegistroTallerForm, WizardPaso2Form, WizardPaso3Form, InvitarTecnicoForm
)


def _get_registro_class():
    """Importa RegistroTaller desde el schema publico."""
    from django.apps import apps
    # RegistroTaller vive en el schema publico (shared app)
    # Lo importamos directamente del modelo del schema publico
    try:
        from tenants.models_registro import RegistroTaller
        return RegistroTaller
    except ImportError:
        from .models_onboarding_public import RegistroTaller
        return RegistroTaller


def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing/index.html', {
        'planes': settings.PLANES,
        'features': [
            {'icono': 'bi-clipboard-check', 'titulo': 'Ordenes de reparacion',
             'desc': 'Crea y gestiona tickets en segundos. Numero correlativo automatico.'},
            {'icono': 'bi-link-45deg', 'titulo': 'Link de seguimiento',
             'desc': 'El cliente ve el estado de su equipo en tiempo real, sin llamarte.'},
            {'icono': 'bi-bell', 'titulo': 'Notificaciones automaticas',
             'desc': 'Email automatico al cliente en cada cambio de estado.'},
            {'icono': 'bi-people', 'titulo': 'Multi-tecnico',
             'desc': 'Asigna ordenes a distintos tecnicos.'},
            {'icono': 'bi-shop', 'titulo': 'Tienda virtual',
             'desc': 'Publica productos y servicios en tu propia vitrina digital.'},
            {'icono': 'bi-phone', 'titulo': '100% en la nube',
             'desc': 'Funciona desde cualquier dispositivo. Sin instalaciones.'},
        ]
    })

import secrets
from django.core.cache import cache

def login_publico(request):
    """
    Login en el schema publico.
    El usuario escribe usuario + password + slug del taller.
    El sistema genera un token temporal y redirige al subdominio.
    """
    if request.method == 'POST':
        username    = request.POST.get('username', '').strip()
        password    = request.POST.get('password', '').strip()
        slug_taller = request.POST.get('slug_taller', '').strip().lower().replace('-', '_')

        # 1. Buscar el taller en el schema publico
        try:
            taller = Taller.objects.get(schema_name=slug_taller, activo=True)
        except Taller.DoesNotExist:
            return render(request, 'onboarding/login_publico.html', {
                'error': 'No existe un taller con ese nombre.',
                'post': request.POST,
            })

        # 2. Verificar credenciales dentro del schema del taller
        from django_tenants.utils import schema_context
        with schema_context(slug_taller):
            from django.contrib.auth import authenticate as auth_check
            usuario = auth_check(request, username=username, password=password)

        if not usuario:
            return render(request, 'onboarding/login_publico.html', {
                'error': 'Usuario o contrasena incorrectos.',
                'post': request.POST,
            })

        # 3. Generar token de un solo uso (valido por 30 segundos)
        token = secrets.token_urlsafe(32)
        cache.set(f'login_token_{token}', {
            'user_id':  usuario.id,
            'username': usuario.username,
            'schema':   slug_taller,
        }, timeout=30)

        # 4. Redirigir al subdominio con el token
        dominio = Dominio.objects.filter(tenant=taller, is_primary=True).first()
        if not dominio:
            return render(request, 'onboarding/login_publico.html', {
                'error': 'El taller no tiene dominio configurado.',
                'post': request.POST,
            })

        # Construir URL del subdominio
        host = dominio.domain  # ej: demo-taller.localhost
        port = request.get_port()
        redirect_url = f"http://{host}:{port}/auth/token/{token}/"
        return redirect(redirect_url)

    return render(request, 'onboarding/login_publico.html', {
        'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
    })


def consumir_token_login(request, token):
    """
    Vista que vive en el schema del TENANT.
    Recibe el token, valida, inicia sesion y redirige al dashboard.
    """
    from django.core.cache import cache
    from django.contrib.auth import login as auth_login
    from django.db import connection

    datos = cache.get(f'login_token_{token}')

    if not datos:
        messages.error(request, 'El link de acceso expiro o ya fue usado. Ingresa nuevamente.')
        return redirect('login_publico')

    # Validar que el token corresponde al schema activo
    if datos['schema'] != connection.schema_name:
        messages.error(request, 'Token invalido para este taller.')
        return redirect('login_publico')

    # Eliminar el token (un solo uso)
    cache.delete(f'login_token_{token}')

    # Buscar el usuario en este schema y loguearlo
    try:
        from django.contrib.auth.models import User
        usuario = User.objects.get(id=datos['user_id'])
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado en este taller.')
        return redirect('login_publico')

    # Login sin necesidad de password (ya fue verificado)
    usuario.backend = 'django.contrib.auth.backends.ModelBackend'
    auth_login(request, usuario)

    messages.success(request, f'Bienvenido, {usuario.first_name or usuario.username}!')
    return redirect('dashboard')


def registro_taller(request):
    
    if request.user.is_authenticated:
        return redirect('dashboard')
    plan_inicial = request.GET.get('plan', 'profesional')
    form = RegistroTallerForm(request.POST or None, initial={'plan_elegido': plan_inicial})
    if request.method == 'POST' and form.is_valid():
        request.session.flush()   # limpiar sesion previa
        # Guardar en sesion para el wizard (no en BD aun)
        request.session['onboarding_data'] = {
            'nombre_taller': form.cleaned_data['nombre_taller'],
            'nombre_dueno':  form.cleaned_data['nombre_dueno'],
            'email':         form.cleaned_data['email'],
            'telefono':      form.cleaned_data['telefono'],
            'ciudad':        form.cleaned_data.get('ciudad', ''),
            'plan_elegido':  form.cleaned_data['plan_elegido'],
        }
        request.session['onboarding_paso'] = 2
        # Enviar email de confirmacion (simplificado)
        email = form.cleaned_data['email']
        import uuid
        token = str(uuid.uuid4())
        request.session['onboarding_token'] = token
        _enviar_email_simple(
            email,
            'Confirma tu registro en TecniTrack',
            f'Hola {form.cleaned_data["nombre_dueno"]},\n\nContinua tu registro aqui:\n{settings.SITE_URL}/registro/configurar/2/'
        )
        return redirect('registro_confirmacion_enviada', email=email)
    return render(request, 'onboarding/registro.html', {
        'form': form, 'plan_inicial': plan_inicial, 'planes': settings.PLANES
    })


def registro_confirmacion_enviada(request, email):
    return render(request, 'onboarding/confirmacion_enviada.html', {'email': email})


def confirmar_email(request, token):
    messages.success(request, 'Email confirmado. Configura tu cuenta.')
    return redirect('onboarding_wizard', paso=2)


def onboarding_wizard(request, paso):
    if paso == 2:
        return _wizard_paso2(request)
    elif paso == 3:
        return _wizard_paso3(request)
    return redirect('onboarding_wizard', paso=2)


def _wizard_paso2(request):
    datos = request.session.get('onboarding_data',{})
    username_sugerido = slugify(datos.get('nombre_dueno', 'usuario').split()[0]).replace('_', '-')
    form = WizardPaso2Form(request.POST or None, initial={'username': username_sugerido})
    if request.method == 'POST' and form.is_valid():
        request.session['onboarding_paso2'] = {
            'username': form.cleaned_data['username'],
            'password': form.cleaned_data['password1'],
        }
        return redirect('onboarding_wizard', paso=3)
    return render(request, 'onboarding/wizard.html', {
        'paso': 2, 'total_pasos': 3, 'form': form,
        'registro': type('R', (), datos)(),
        'titulo_paso': 'Crea tus credenciales', 'desc_paso': 'Con esto ingresaras al sistema.',
    })


def _wizard_paso3(request):
    datos  = request.session.get('onboarding_data')
    paso2  = request.session.get('onboarding_paso2')
    
    # ── GUARDIA: si la sesion se perdio, volver al inicio ──────────────────
    if not datos or 'nombre_taller' not in datos:
        messages.error(request, 'La sesion expiro. Por favor completa el registro desde el inicio.')
        return redirect('registro_taller')

    if not paso2:
        messages.error(request, 'Faltan los datos del paso 2. Vuelve atras.')
        return redirect('onboarding_wizard', paso=2)

   

    form = WizardPaso3Form(request.POST or None, initial={
        'telefono_taller': datos.get('telefono', ''), 'notif_email': True
    })

    if request.method == 'POST' and form.is_valid():
        # ── CREAR EL TENANT (SCHEMA DE POSTGRESQL) ──────────────────────────
        nombre_taller = datos['nombre_taller']
        slug_base = slugify(nombre_taller)[:30]
        schema = slug_base.replace('_', '-')
        # Asegurar unicidad del schema
        contador = 1
        schema_final = schema
        while Taller.objects.filter(schema_name=schema_final).exists():
            schema_final = f"{schema}_{contador}"
            contador += 1

        # 1. Crear el Taller (Tenant) — esto crea el schema en PostgreSQL
        taller = Taller(
            schema_name=schema_final,
            nombre=nombre_taller,
            email=datos['email'],
            telefono=form.cleaned_data['telefono_taller'],
            direccion=form.cleaned_data.get('direccion', ''),
            plan=datos.get('plan_elegido', 'profesional'),
            activo=True,
            notif_email=form.cleaned_data.get('notif_email', True),
            mensaje_bienvenida=form.cleaned_data.get('mensaje_bienvenida', '') or
                'Hemos recibido tu equipo. Te notificaremos en cada etapa.',
        )
        taller.save()  # <-- django-tenants crea el schema aqui

        # 2. Crear el dominio del taller (subdominio)
        dominio = f"{schema_final}.localhost"
        Dominio.objects.create(domain=dominio, tenant=taller, is_primary=True)

        # 3. Activar el schema del taller para crear objetos dentro de el
        from django_tenants.utils import schema_context
        nombre_parts = datos['nombre_dueno'].strip().split(' ', 1)
        first_name = nombre_parts[0]
        last_name  = nombre_parts[1] if len(nombre_parts) > 1 else ''

        with schema_context(schema_final):
            # 4. Crear el usuario dentro del schema del taller
            usuario = User.objects.create_user(
                username=paso2['username'],
                email=datos['email'],
                password=paso2['password'],
                first_name=first_name,
                last_name=last_name,
            )
            # 5. Crear el perfil de usuario (rol: dueno)
            from taller.models import PerfilUsuario, Suscripcion
            PerfilUsuario.objects.create(usuario=usuario, rol='dueno')
            # 6. Crear la suscripcion en trial
            Suscripcion.objects.create(plan=datos.get('plan_elegido', 'profesional'))

        # 7. Limpiar sesion
        for key in ['onboarding_data', 'onboarding_paso2', 'onboarding_paso', 'onboarding_token']:
            request.session.pop(key, None)

        # 8. Enviar email de bienvenida
        _enviar_email_simple(
            datos['email'],
            f'Bienvenido a TecniTrack, {first_name}!',
            f'Tu taller esta listo. Accede en: {settings.SITE_URL}\nUsuario: {paso2["username"]}'
        )

        messages.success(request, f'Bienvenido {first_name}! Tu taller ha sido creado.')
        # Login en el schema del taller requiere redirigir al subdominio
        return redirect('onboarding_completado')

    return render(request, 'onboarding/wizard.html', {
        'paso': 3, 'total_pasos': 3, 'form': form,
        'registro': type('R', (), datos)(),
        'titulo_paso': 'Personaliza tu taller',
        'desc_paso': 'Estos datos apareceran en los emails de tus clientes.',
    })


def onboarding_completado(request):
    return render(request, 'onboarding/completado.html')


@login_required
def invitar_tecnico(request):
    from taller.models import InvitacionTecnico
    form = InvitarTecnicoForm(request.POST or None)
    invitaciones = InvitacionTecnico.objects.order_by('-creada_en')[:10]
    if request.method == 'POST' and form.is_valid():
        inv = InvitacionTecnico.objects.create(
            email=form.cleaned_data['email'],
            rol=form.cleaned_data['rol'],
            creada_por=request.user,
        )
        taller = connection.tenant
        url = f"{settings.SITE_URL}/invitacion/{inv.token}/"
        _enviar_email_simple(
            inv.email,
            f'Te invitaron a {taller.nombre} en TecniTrack',
            f'Acepta la invitacion aqui: {url}'
        )
        messages.success(request, f'Invitacion enviada a {inv.email}.')
        return redirect('invitar_tecnico')
    return render(request, 'onboarding/invitar_tecnico.html', {
        'form': form, 'invitaciones': invitaciones, 'taller': connection.tenant
    })


def aceptar_invitacion(request, token):
    """
    El tecnico acepta la invitacion. Necesitamos saber en que schema
    crear el usuario. El token identifica la invitacion dentro del schema.
    En schema-based tenancy, la invitacion la buscamos en todos los schemas
    o la incluimos en el link con el schema_name del taller.
    """
    # Buscar la invitacion en el schema activo (el link incluye el subdominio del taller)
    from taller.models import InvitacionTecnico
    inv = get_object_or_404(InvitacionTecnico, token=token)
    if not inv.vigente:
        messages.error(request, 'Esta invitacion expiro.')
        return redirect('landing')
    form = WizardPaso2Form(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        nombre_completo = request.POST.get('nombre_completo', form.cleaned_data['username'])
        partes = nombre_completo.split(' ', 1)
        usuario = User.objects.create_user(
            username=form.cleaned_data['username'],
            email=inv.email,
            password=form.cleaned_data['password1'],
            first_name=partes[0],
            last_name=partes[1] if len(partes) > 1 else '',
        )
        from taller.models import PerfilUsuario
        PerfilUsuario.objects.create(usuario=usuario, rol=inv.rol)
        inv.usada = True
        inv.save()
        login(request, usuario)
        taller = connection.tenant
        messages.success(request, f'Bienvenido al equipo de {taller.nombre}!')
        return redirect('dashboard')
    return render(request, 'onboarding/aceptar_invitacion.html', {
        'form': form, 'invitacion': inv
    })


def _enviar_email_simple(to, subject, body):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=True)
    except Exception:
        pass
