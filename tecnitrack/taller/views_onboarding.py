"""
OrdenTec - Views de Onboarding (schema-based tenancy)
Login publico con token + Wizard de registro con redireccion al subdominio.
"""
import secrets, random, string
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
from django.db import connection, IntegrityError


from tenants.models import Taller, Dominio
from .forms_onboarding import (
    RegistroTallerForm, WizardPaso2Form, WizardPaso3Form, InvitarTecnicoForm
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_subdominio_url(request, schema_name, path='/dashboard/'):
    """
    Construye la URL del subdominio del taller.
    En dev:  http://demo-taller.localhost:8000/dashboard/
    En prod: https://demo-taller.ordentec.com/dashboard/
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

# def login_publico(request):
#     if request.method == 'POST':
#         username    = request.POST.get('username', '').strip()
#         password    = request.POST.get('password', '').strip()
#         slug_input  = request.POST.get('slug_taller', '').strip().lower()
#         schema_name = slug_input.replace('-', '_')

#         try:
#             taller = Taller.objects.get(schema_name=schema_name, activo=True)
#         except Taller.DoesNotExist:
#             return render(request, 'onboarding/login_publico.html', {
#                 'error': 'No existe un taller activo con ese nombre.',
#                 'post': request.POST,
#                 'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
#             })

#         from django_tenants.utils import schema_context
#         from django.contrib.auth import authenticate as auth_check

#         with schema_context(schema_name):
#             usuario = auth_check(request, username=username, password=password)

#             # ── VERIFICACION CRITICA: el usuario debe pertenecer a ESTE taller ──
#             if usuario:
#                 from taller.models import PerfilUsuario
#                 tiene_perfil = PerfilUsuario.objects.filter(
#                     usuario=usuario, activo=True
#                 ).exists()
#                 if not tiene_perfil:
#                     usuario = None  # las credenciales son validas, pero no pertenece a este taller

#         if not usuario:
#             return render(request, 'onboarding/login_publico.html', {
#                 'error': 'Usuario o contrasena incorrectos para este taller.',
#                 'post': request.POST,
#                 'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
#             })

#         token = _generar_token_login(usuario, schema_name, timeout=60)
#         url   = _get_subdominio_url(request, schema_name, path=f'/auth/token/{token}/')
#         return redirect(url)

#     return render(request, 'onboarding/login_publico.html', {
#         'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
#     })

OTP_TTL = 300  # 5 minutos


def _generar_otp():
    return ''.join(random.choices(string.digits, k=6))


def login_publico(request):
    """
    Login centralizado con 2FA por email.
    Paso A: usuario + password + slug_taller -> genera OTP y lo envia por email.
    Paso B: el mismo formulario revela un campo OTP -> valida y genera token de login.
    """
    if request.method == 'POST':
        accion = request.POST.get('accion', 'verificar_credenciales')

        # ── PASO A: verificar usuario/password y enviar OTP ──────────────────
        if accion == 'verificar_credenciales':
            username    = request.POST.get('username', '').strip()
            password    = request.POST.get('password', '').strip()
            slug_input  = request.POST.get('slug_taller', '').strip().lower()
            schema_name = slug_input.replace('-', '_')

            # 1. Buscar el taller (igual que antes)
            try:
                taller = Taller.objects.get(schema_name=schema_name, activo=True)
            except Taller.DoesNotExist:
                return render(request, 'onboarding/login_publico.html', {
                    'error': 'No existe un taller activo con ese nombre.',
                    'post':  request.POST,
                    'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
                })

            # 2. Verificar credenciales dentro del schema (igual que antes)
            from django_tenants.utils import schema_context
            from django.contrib.auth import authenticate as auth_check
            from taller.models import PerfilUsuario

            with schema_context(schema_name):
                usuario = auth_check(request, username=username, password=password)
                if usuario:
                    tiene_perfil = PerfilUsuario.objects.filter(
                        usuario=usuario, activo=True
                    ).exists()
                    if not tiene_perfil:
                        usuario = None

            if not usuario:
                return render(request, 'onboarding/login_publico.html', {
                    'error': 'Usuario o contrasena incorrectos para este taller.',
                    'post':  request.POST,
                    'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
                })

            # 3. NUEVO: verificar que el usuario tenga email para el OTP
            if not usuario.email:
                return render(request, 'onboarding/login_publico.html', {
                    'error': 'Tu cuenta no tiene correo configurado. Contacta al dueno del taller.',
                    'post':  request.POST,
                    'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
                })

            # 4. NUEVO: generar OTP y enviarlo por email
            otp_token = secrets.token_urlsafe(16)
            codigo    = _generar_otp()

            cache.set(f'otp_login_{otp_token}', {
                'codigo':   codigo,
                'user_id':  usuario.id,
                'schema':   schema_name,
                'intentos': 0,
            }, timeout=OTP_TTL)

            _enviar_email_simple(
                usuario.email,
                'Tu codigo de verificacion — OrdenTec',
                (
                    f'Hola {usuario.first_name or usuario.username}!\n\n'
                    f'Tu codigo de verificacion es: {codigo}\n\n'
                    f'Expira en 5 minutos. Si no fuiste tu, ignora este correo.'
                )
            )
            
            # 5. NUEVO: re-renderizar el formulario mostrando el campo OTP
            return render(request, 'onboarding/login_publico.html', {
                'mostrar_otp':  True,
                'otp_token':    otp_token,
                'email_oculto': _enmascarar_email(usuario.email),
                'post':         request.POST,
                'talleres':     Taller.objects.filter(activo=True).order_by('nombre'),
            })

        # ── PASO B: verificar el codigo OTP ──────────────────────────────────
        elif accion == 'verificar_otp':
            otp_token  = request.POST.get('otp_token', '').strip()
            codigo_ing = request.POST.get('codigo_otp', '').strip()

            datos = cache.get(f'otp_login_{otp_token}')

            if not datos:
                return render(request, 'onboarding/login_publico.html', {
                    'error':    'El codigo expiro. Ingresa tus credenciales nuevamente.',
                    'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
                })

            if datos['intentos'] >= 5:
                cache.delete(f'otp_login_{otp_token}')
                return render(request, 'onboarding/login_publico.html', {
                    'error':    'Demasiados intentos fallidos. Ingresa tus credenciales nuevamente.',
                    'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
                })

            if codigo_ing != datos['codigo']:
                datos['intentos'] += 1
                cache.set(f'otp_login_{otp_token}', datos, timeout=OTP_TTL)
                return render(request, 'onboarding/login_publico.html', {
                    'error':       'Codigo incorrecto. Intenta nuevamente.',
                    'mostrar_otp': True,
                    'otp_token':   otp_token,
                    'talleres':    Taller.objects.filter(activo=True).order_by('nombre'),
                })

            # Codigo correcto -> eliminar OTP y generar token de login (igual que antes)
            cache.delete(f'otp_login_{otp_token}')

            try:
                usuario = User.objects.get(id=datos['user_id'])
            except User.DoesNotExist:
                return redirect('login_publico')

            login_token = _generar_token_login(usuario, datos['schema'], timeout=60)
            url = _get_subdominio_url(request, datos['schema'], path=f'/auth/token/{login_token}/')
            return redirect(url)

    return render(request, 'onboarding/login_publico.html', {
        'talleres': Taller.objects.filter(activo=True).order_by('nombre'),
    })

def _enmascarar_email(email):
    """ejemplo: dueno@gmail.com -> du***@gmail.com"""
    try:
        local, dominio = email.split('@')
        if len(local) <= 2:
            return f"{local[0]}***@{dominio}"
        return f"{local[:2]}***@{dominio}"
    except Exception:
        return email


def consumir_token_login(request, token):
    datos = cache.get(f'login_token_{token}')

    if not datos:
        messages.error(request, 'El link de acceso expiro o ya fue usado. Ingresa nuevamente.')
        return redirect('login_publico')

    if datos['schema'] != connection.schema_name:
        messages.error(request, 'Token invalido para este taller.')
        return redirect('login_publico')

    cache.delete(f'login_token_{token}')

    try:
        usuario = User.objects.get(id=datos['user_id'])
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('login_publico')

    # ── VERIFICACION CRITICA otra vez, aqui dentro del schema del tenant ──
    from taller.models import PerfilUsuario
    if not PerfilUsuario.objects.filter(usuario=usuario, activo=True).exists():
        messages.error(request, 'No tienes acceso a este taller.')
        return redirect('login_publico')

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

WIZARD_TTL = 86400  # 24 horas

def registro_taller(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    plan_inicial = request.GET.get('plan', 'profesional')
    form = RegistroTallerForm(request.POST or None, initial={'plan_elegido': plan_inicial})

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].lower().strip()

        if cache.get(f'email_reservado_{email}'):
            form.add_error('email', 'Ya tienes un registro en proceso con este correo. Revisa tu bandeja de entrada.')
            return render(request, 'onboarding/registro.html', {
                'form': form, 'plan_inicial': plan_inicial, 'planes': settings.PLANES
            })

        token = secrets.token_urlsafe(24)

        wizard_state = {
            'paso_actual': 2,   # el paso 1 ya se completo, sigue el 2
            'datos': {
                'nombre_taller': form.cleaned_data['nombre_taller'],
                'nombre_dueno':  form.cleaned_data['nombre_dueno'],
                'email':         email,
                'telefono':      form.cleaned_data['telefono'],
                'ciudad':        form.cleaned_data.get('ciudad', ''),
                'plan_elegido':  form.cleaned_data['plan_elegido'],
            },
            'paso2': None,
            'completado': False,
        }

        cache.set(f'email_reservado_{email}', token, timeout=WIZARD_TTL)
        cache.set(f'wizard_{token}', wizard_state, timeout=WIZARD_TTL)

        _enviar_email_simple(
            email,
            'Confirma tu registro en OrdenTec',
            (
                f'Hola {form.cleaned_data["nombre_dueno"]}!\n\n'
                f'Continua tu registro aqui (valido por 24 horas):\n'
                f'{settings.SITE_URL}/registro/continuar/{token}/\n\n'
                f'Puedes cerrar esta pestana y volver a este link en cualquier momento '
                f'para seguir donde quedaste.'
            )
        )
        return redirect('registro_confirmacion_enviada', email=email)

    return render(request, 'onboarding/registro.html', {
        'form': form, 'plan_inicial': plan_inicial, 'planes': settings.PLANES
    })

def registro_confirmacion_enviada(request, email):
    return render(request, 'onboarding/confirmacion_enviada.html', {'email': email})

def continuar_registro(request, token):
    """
    Punto de entrada unico del wizard. Recupera el estado completo desde
    cache usando el token (no depende de la sesion del navegador).
    El usuario puede cerrar el navegador y volver a este mismo link
    en cualquier momento, sin importar el dispositivo.
    """
    estado = cache.get(f'wizard_{token}')

    if not estado:
        messages.error(request, 'Este link expiro o ya completaste tu registro. Si necesitas ayuda, registrate nuevamente.')
        return redirect('registro_taller')

    if estado.get('completado'):
        messages.info(request, 'Este registro ya fue completado. Inicia sesion con tus credenciales.')
        return redirect('login_publico')

    paso = estado['paso_actual']

    if paso == 2:
        return _wizard_paso2(request, token, estado)
    elif paso == 3:
        return _wizard_paso3(request, token, estado)

    # Fallback de seguridad
    return redirect('registro_taller')


# ─── WIZARD — PASO 2 ─────────────────────────────────────────────────────────

def _wizard_paso2(request, token, estado):
    datos = estado['datos']

    username_sugerido = slugify(
        datos.get('nombre_dueno', 'usuario').split()[0]
    ).replace('-', '_')

    form = WizardPaso2Form(request.POST or None, initial={'username': username_sugerido})

    if request.method == 'POST' and form.is_valid():
        estado['paso2'] = {
            'username': form.cleaned_data['username'],
            'password': form.cleaned_data['password1'],
        }
        estado['paso_actual'] = 3
        cache.set(f'wizard_{token}', estado, timeout=WIZARD_TTL)
        return redirect('continuar_registro', token=token)

    return render(request, 'onboarding/wizard.html', {
        'paso': 2, 'total_pasos': 3, 'form': form,
        'token': token,
        'registro': type('R', (), datos)(),
        'titulo_paso': 'Crea tus credenciales de acceso',
        'desc_paso':   'Con esto ingresaras al sistema todos los dias.',
    })

# ─── WIZARD — PASO 3 ─────────────────────────────────────────────────────────

def _wizard_paso3(request, token, estado):
    datos = estado['datos']
    paso2 = estado['paso2']

    if not paso2 or 'username' not in paso2:
        # No deberia pasar, pero por seguridad regresamos al paso 2
        estado['paso_actual'] = 2
        cache.set(f'wizard_{token}', estado, timeout=WIZARD_TTL)
        return redirect('continuar_registro', token=token)

    form = WizardPaso3Form(request.POST or None, initial={
        'telefono_taller': datos.get('telefono', ''),
        'notif_email': True,
    })

    if request.method == 'POST' and form.is_valid():
        from django.db import IntegrityError

        # Verificacion final atomica
        if Taller.objects.filter(email=datos['email']).exists():
            messages.error(request, 'Ya existe un taller registrado con este correo.')
            cache.delete(f'wizard_{token}')
            cache.delete(f'email_reservado_{datos["email"]}')
            return redirect('registro_taller')

        slug_base    = slugify(datos['nombre_taller'])[:30].replace('-', '_')
        schema_final = slug_base
        contador = 1
        while Taller.objects.filter(schema_name=schema_final).exists():
            schema_final = f"{slug_base}_{contador}"
            contador += 1

        taller = Taller(
            schema_name = schema_final,
            nombre      = datos['nombre_taller'],
            email       = datos['email'],
            telefono    = form.cleaned_data['telefono_taller'],
            direccion   = form.cleaned_data.get('direccion', ''),
            plan        = datos.get('plan_elegido', 'profesional'),
            activo      = True,
            notif_email = form.cleaned_data.get('notif_email', True),
            mensaje_bienvenida=(
                form.cleaned_data.get('mensaje_bienvenida') or
                'Hemos recibido tu equipo. Te notificaremos en cada etapa.'
            ),
        )

        try:
            taller.save()
        except IntegrityError:
            messages.error(request, 'Ya existe un taller registrado con este correo.')
            cache.delete(f'wizard_{token}')
            cache.delete(f'email_reservado_{datos["email"]}')
            return redirect('registro_taller')

        slug_dominio = schema_final.replace('_', '-')
        dominio_str  = f"{slug_dominio}.localhost" if settings.DEBUG else f"{slug_dominio}.OrdenTec.com"

        Dominio.objects.create(domain=dominio_str, tenant=taller, is_primary=True)

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

        # Marcar como completado y liberar reservas
        estado['completado'] = True
        cache.set(f'wizard_{token}', estado, timeout=300)  # se conserva 5 min por si hay doble-click
        cache.delete(f'email_reservado_{datos["email"]}')

        login_token = _generar_token_login(usuario, schema_final, timeout=120)
        url = _get_subdominio_url(request, schema_final, path=f'/auth/token/{login_token}/')

        _enviar_email_simple(
            datos['email'],
            f'Bienvenido a OrdenTec, {first_name}!',
            (
                f'Tu taller "{datos["nombre_taller"]}" esta listo.\n\n'
                f'Accede en: http://{dominio_str}:8000\n'
                f'Usuario: {paso2["username"]}\n\n'
                f'Tienes 30 dias de prueba gratuita.'
            )
        )

        return redirect(url)

    return render(request, 'onboarding/wizard.html', {
        'paso': 3, 'total_pasos': 3, 'form': form,
        'token': token,
        'registro': type('R', (), datos)(),
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
            f'Te invitaron a {taller.nombre} en OrdenTec',
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