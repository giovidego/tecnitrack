"""
TecniTrack - Views de Onboarding (schema-based tenancy)
Login publico con token + Wizard de registro con redireccion al subdominio.
"""
import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from django.db import connection

from tenants.models import Taller, Dominio
from .forms_onboarding import (
    RegistroTallerForm, WizardPaso2Form, WizardPaso3Form, InvitarTecnicoForm
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_subdominio_url(request, schema_name, path='/dashboard/'):
    """
    Construye la URL del subdominio del taller.
    En dev:  http://demo-taller.localhost:8000/dashboard/
    En prod: https://demo-taller.tecnitrack.cl/dashboard/
    """
    dominio = Dominio.objects.filter(
        tenant__schema_name=schema_name, is_primary=True
    ).first()
    if not dominio:
        return path

    scheme = 'https' if not settings.DEBUG else 'http'
    host   = dominio.domain
    port   = request.get_port()

    # En produccion no poner el puerto
    if (scheme == 'http'  and port == '80') or \
       (scheme == 'https' and port == '443'):
        return f"{scheme}://{host}{path}"

    return f"{scheme}://{host}:{port}{path}"


def _generar_token_login(usuario, schema_name, timeout=60):
    """
    Genera un token de un solo uso para transferir la sesion
    del schema publico al schema del taller.
    Valido por 60 segundos.
    """
    token = secrets.token_urlsafe(32)
    cache.set(f'login_token_{token}', {
        'user_id':  usuario.id,
        'username': usuario.username,
        'schema':   schema_name,
    }, timeout=timeout)
    return token


def _enviar_email_simple(to, subject, body):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=True)
    except Exception:
        pass


# ─── LOGIN PUBLICO ────────────────────────────────────────────────────────────

def login_publico(request):
    """
    Login en el schema publico (localhost:8000/login/).
    El usuario escribe slug del taller + usuario + contrasena.
    El sistema verifica en el schema correcto y redirige al subdominio.
    """
    if request.method == 'POST':
        username    = request.POST.get('username', '').strip()
        password    = request.POST.get('password', '').strip()
        slug_input  = request.POST.get('slug_taller', '').strip().lower()
        # Normalizar: demo-taller o demo_taller -> demo_taller
        schema_name = slug_input.replace('-', '_')

        # 1. Buscar el taller
        try:
            taller = Taller.objects.get(schema_name=schema_name, activo=True)
        except Taller.DoesNotExist:
            return render(request, 'onboarding/login_publico.html', {
                'error': 'No existe un taller activo con ese nombre.',
                'post': request.POST,
                'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
            })

        # 2. Verificar credenciales DENTRO del schema del taller
        from django_tenants.utils import schema_context
        from django.contrib.auth import authenticate as auth_check
        with schema_context(schema_name):
            usuario = auth_check(request, username=username, password=password)

        if not usuario:
            return render(request, 'onboarding/login_publico.html', {
                'error': 'Usuario o contrasena incorrectos.',
                'post': request.POST,
                'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
            })

        # 3. Generar token de un solo uso
        token = _generar_token_login(usuario, schema_name, timeout=60)

        # 4. Redirigir al subdominio con el token
        url = _get_subdominio_url(request, schema_name, path=f'/auth/token/{token}/')
        return redirect(url)

    return render(request, 'onboarding/login_publico.html', {
        'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
    })


def consumir_token_login(request, token):
    """
    Vista en el schema del TENANT (demo-taller.localhost:8000/auth/token/<token>/).
    Valida el token, inicia la sesion y redirige al dashboard.
    """
    datos = cache.get(f'login_token_{token}')

    if not datos:
        messages.error(request, 'El link de acceso expiro o ya fue usado. Ingresa nuevamente.')
        return redirect('login_publico')

    # Validar que el token corresponde a este schema
    if datos['schema'] != connection.schema_name:
        messages.error(request, 'Token invalido para este taller.')
        cache.delete(f'login_token_{token}')
        return redirect('login_publico')

    # Eliminar el token (un solo uso)
    cache.delete(f'login_token_{token}')

    # Buscar el usuario en este schema
    try:
        usuario = User.objects.get(id=datos['user_id'])
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado en este taller.')
        return redirect('login_publico')

    # Login sin password (ya fue verificado en el schema publico)
    usuario.backend = 'django.contrib.auth.backends.ModelBackend'
    auth_login(request, usuario)

    messages.success(request, f'Bienvenido, {usuario.first_name or usuario.username}!')
    return redirect('dashboard')


# ─── LANDING ──────────────────────────────────────────────────────────────────

def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing/index.html', {
        'planes': settings.PLANES,
        'features': [
            {'icono': 'bi-clipboard-check', 'titulo': 'Ordenes de reparacion',
             'desc': 'Crea y gestiona tickets en segundos. Numero correlativo automatico.'},
            {'icono': 'bi-link-45deg',      'titulo': 'Link de seguimiento',
             'desc': 'El cliente ve el estado de su equipo en tiempo real, sin llamarte.'},
            {'icono': 'bi-bell',            'titulo': 'Notificaciones automaticas',
             'desc': 'Email automatico al cliente en cada cambio de estado.'},
            {'icono': 'bi-people',          'titulo': 'Multi-tecnico',
             'desc': 'Asigna ordenes a distintos tecnicos.'},
            {'icono': 'bi-shop',            'titulo': 'Tienda virtual',
             'desc': 'Publica productos y servicios en tu propia vitrina digital.'},
            {'icono': 'bi-phone',           'titulo': '100% en la nube',
             'desc': 'Funciona desde cualquier dispositivo. Sin instalaciones.'},
        ]
    })


# ─── REGISTRO — PASO 1 ───────────────────────────────────────────────────────

def registro_taller(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    plan_inicial = request.GET.get('plan', 'profesional')
    form = RegistroTallerForm(request.POST or None, initial={'plan_elegido': plan_inicial})

    if request.method == 'POST' and form.is_valid():
        # Limpiar sesion previa y guardar datos del paso 1
        request.session.flush()
        request.session['onboarding_data'] = {
            'nombre_taller': form.cleaned_data['nombre_taller'],
            'nombre_dueno':  form.cleaned_data['nombre_dueno'],
            'email':         form.cleaned_data['email'],
            'telefono':      form.cleaned_data['telefono'],
            'ciudad':        form.cleaned_data.get('ciudad', ''),
            'plan_elegido':  form.cleaned_data['plan_elegido'],
        }
        request.session.modified = True

        email = form.cleaned_data['email']
        _enviar_email_simple(
            email,
            'Confirma tu registro en TecniTrack',
            f'Continua tu registro aqui:\n{settings.SITE_URL}/registro/configurar/2/'
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


# ─── WIZARD — PASO 2 ─────────────────────────────────────────────────────────

def onboarding_wizard(request, paso):
    if paso == 2:
        return _wizard_paso2(request)
    elif paso == 3:
        return _wizard_paso3(request)
    return redirect('onboarding_wizard', paso=2)


def _wizard_paso2(request):
    datos = request.session.get('onboarding_data', {})

    # Guardia: sesion perdida
    if not datos or 'nombre_taller' not in datos:
        messages.error(request, 'Sesion expirada. Por favor registrate nuevamente.')
        return redirect('registro_taller')

    username_sugerido = slugify(
        datos.get('nombre_dueno', 'usuario').split()[0]
    ).replace('-', '_')

    form = WizardPaso2Form(request.POST or None, initial={'username': username_sugerido})

    if request.method == 'POST' and form.is_valid():
        request.session['onboarding_paso2'] = {
            'username': form.cleaned_data['username'],
            'password': form.cleaned_data['password1'],
        }
        request.session.modified = True
        return redirect('onboarding_wizard', paso=3)

    return render(request, 'onboarding/wizard.html', {
        'paso': 2, 'total_pasos': 3, 'form': form,
        'registro': type('R', (), datos)(),
        'titulo_paso': 'Crea tus credenciales de acceso',
        'desc_paso':   'Con esto ingresaras al sistema todos los dias.',
    })


# ─── WIZARD — PASO 3 ─────────────────────────────────────────────────────────

def _wizard_paso3(request):
    datos = request.session.get('onboarding_data', {})
    paso2 = request.session.get('onboarding_paso2', {})

    # Guardias
    if not datos or 'nombre_taller' not in datos:
        messages.error(request, 'Sesion expirada. Por favor registrate nuevamente.')
        return redirect('registro_taller')

    if not paso2 or 'username' not in paso2:
        messages.error(request, 'Faltan los datos del paso anterior.')
        return redirect('onboarding_wizard', paso=2)

    form = WizardPaso3Form(request.POST or None, initial={
        'telefono_taller': datos.get('telefono', ''),
        'notif_email': True,
    })

    if request.method == 'POST' and form.is_valid():

        # ── 1. Generar schema_name unico ─────────────────────────────────────
        slug_base    = slugify(datos['nombre_taller'])[:30].replace('-', '_')
        schema_final = slug_base
        contador = 1
        while Taller.objects.filter(schema_name=schema_final).exists():
            schema_final = f"{slug_base}_{contador}"
            contador += 1

        # ── 2. Crear el Taller (django-tenants crea el schema PostgreSQL) ─────
        taller = Taller(
            schema_name       = schema_final,
            nombre            = datos['nombre_taller'],
            email             = datos['email'],
            telefono          = form.cleaned_data['telefono_taller'],
            direccion         = form.cleaned_data.get('direccion', ''),
            plan              = datos.get('plan_elegido', 'profesional'),
            activo            = True,
            notif_email       = form.cleaned_data.get('notif_email', True),
            mensaje_bienvenida= (
                form.cleaned_data.get('mensaje_bienvenida') or
                'Hemos recibido tu equipo. Te notificaremos en cada etapa.'
            ),
        )
        taller.save()  # <- crea el schema en PostgreSQL

        # ── 3. Crear el dominio del taller ────────────────────────────────────
        # En dev:  demo-taller.localhost
        # En prod: demo-taller.tecnitrack.cl
        slug_dominio = schema_final.replace('_', '-')
        if settings.DEBUG:
            dominio_str = f"{slug_dominio}.localhost"
        else:
            dominio_str = f"{slug_dominio}.tecnitrack.cl"

        Dominio.objects.create(
            domain     = dominio_str,
            tenant     = taller,
            is_primary = True,
        )

        # ── 4. Crear User, Perfil y Suscripcion DENTRO del schema ─────────────
        from django_tenants.utils import schema_context
        nombre_parts = datos['nombre_dueno'].strip().split(' ', 1)
        first_name   = nombre_parts[0]
        last_name    = nombre_parts[1] if len(nombre_parts) > 1 else ''

        with schema_context(schema_final):
            usuario = User.objects.create_user(
                username   = paso2['username'],
                email      = datos['email'],
                password   = paso2['password'],
                first_name = first_name,
                last_name  = last_name,
            )
            from taller.models import PerfilUsuario, Suscripcion
            PerfilUsuario.objects.create(usuario=usuario, rol='dueno')
            Suscripcion.objects.create(plan=datos.get('plan_elegido', 'profesional'))

        # ── 5. Limpiar sesion ─────────────────────────────────────────────────
        for key in ['onboarding_data', 'onboarding_paso2',
                    'onboarding_paso', 'onboarding_token']:
            request.session.pop(key, None)

        # ── 6. Generar token de login y redirigir al subdominio ───────────────
        #    Mismo mecanismo que el login publico: token de un solo uso
        token = _generar_token_login(usuario, schema_final, timeout=120)
        url   = _get_subdominio_url(request, schema_final,
                                    path=f'/auth/token/{token}/')

        # ── 7. Email de bienvenida ────────────────────────────────────────────
        _enviar_email_simple(
            datos['email'],
            f'Bienvenido a TecniTrack, {first_name}!',
            (
                f'Tu taller "{datos["nombre_taller"]}" esta listo.\n\n'
                f'Accede en: http://{dominio_str}:8000\n'
                f'Usuario: {paso2["username"]}\n\n'
                f'Tienes 30 dias de prueba gratuita.'
            )
        )

        # Redirigir directamente al subdominio (el token ya tiene la sesion)
        return redirect(url)

    return render(request, 'onboarding/wizard.html', {
        'paso':        3,
        'total_pasos': 3,
        'form':        form,
        'registro':    type('R', (), datos)(),
        'titulo_paso': 'Personaliza tu taller',
        'desc_paso':   'Estos datos apareceran en los emails de tus clientes.',
    })


def onboarding_completado(request):
    return render(request, 'onboarding/completado.html')


# ─── INVITACIONES ─────────────────────────────────────────────────────────────

@login_required
def invitar_tecnico(request):
    from taller.models import InvitacionTecnico
    form         = InvitarTecnicoForm(request.POST or None)
    invitaciones = InvitacionTecnico.objects.order_by('-creada_en')[:20]

    if request.method == 'POST' and form.is_valid():
        inv = InvitacionTecnico.objects.create(
            email      = form.cleaned_data['email'],
            rol        = form.cleaned_data['rol'],
            creada_por = request.user,
        )
        taller = connection.tenant
        url    = f"{settings.SITE_URL}/invitacion/{inv.token}/"
        _enviar_email_simple(
            inv.email,
            f'Te invitaron a {taller.nombre} en TecniTrack',
            f'Acepta la invitacion aqui:\n{url}\n\nExpira en 7 dias.'
        )
        messages.success(request, f'Invitacion enviada a {inv.email}.')
        return redirect('invitar_tecnico')

    return render(request, 'onboarding/invitar_tecnico.html', {
        'form':        form,
        'invitaciones': invitaciones,
        'taller':      connection.tenant,
    })


def aceptar_invitacion(request, token):
    """
    Vista en el schema PUBLICO.
    Busca la invitacion en el schema del taller correspondiente,
    crea el usuario y redirige al subdominio via token de login.
    """
    from django_tenants.utils import schema_context
    from taller.models import InvitacionTecnico, PerfilUsuario

    # ── 1. Resolver a qué taller pertenece el token ───────────────────────
    # El token es UUID unico global, buscamos en todos los schemas
    taller_encontrado = None
    inv_data          = None

    for taller in Taller.objects.filter(activo=True):
        with schema_context(taller.schema_name):
            inv = InvitacionTecnico.objects.filter(token=token).first()
            if inv:
                taller_encontrado = taller
                inv_data          = {
                    'id':         inv.id,
                    'email':      inv.email,
                    'rol':        inv.rol,
                    'vigente':    inv.vigente,
                    'schema':     taller.schema_name,
                    'nombre_taller': taller.nombre,
                }
                break

    if not taller_encontrado:
        messages.error(request, 'Esta invitacion no existe o ya fue usada.')
        return redirect('landing')

    if not inv_data['vigente']:
        messages.error(request, 'Esta invitacion expiro o ya fue usada.')
        return redirect('landing')

    form = WizardPaso2Form(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        nombre_completo = request.POST.get('nombre_completo', '').strip()
        partes     = nombre_completo.split(' ', 1) if nombre_completo else [form.cleaned_data['username'], '']
        first_name = partes[0]
        last_name  = partes[1] if len(partes) > 1 else ''
        schema     = inv_data['schema']

        # ── 2. Verificar que el username no exista en ese schema ──────────
        with schema_context(schema):
            if User.objects.filter(username=form.cleaned_data['username']).exists():
                form.add_error('username', 'Ese nombre de usuario ya existe en este taller.')
                return render(request, 'onboarding/aceptar_invitacion.html', {
                    'form': form, 'inv': inv_data,
                })

        # ── 3. Crear usuario y perfil DENTRO del schema del taller ────────
        with schema_context(schema):
            usuario = User.objects.create_user(
                username   = form.cleaned_data['username'],
                email      = inv_data['email'],
                password   = form.cleaned_data['password1'],
                first_name = first_name,
                last_name  = last_name,
            )
            PerfilUsuario.objects.create(usuario=usuario, rol=inv_data['rol'])

            # Marcar invitacion como usada
            InvitacionTecnico.objects.filter(token=token).update(usada=True)

        # ── 4. Generar token de login y redirigir al subdominio ───────────
        login_token = _generar_token_login(usuario, schema, timeout=120)
        url         = _get_subdominio_url(request, schema,
                                          path=f'/auth/token/{login_token}/')
        return redirect(url)

    return render(request, 'onboarding/aceptar_invitacion.html', {
        'form': form,
        'inv':  inv_data,
    })