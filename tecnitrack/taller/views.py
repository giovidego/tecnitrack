"""
OrdenTec - Views del taller (schema privado del tenant)
Sin referencias a Taller FK - el schema ya aísla los datos.
connection.tenant da acceso al objeto Taller activo cuando se necesita.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import connection
from django.conf import settings

from .models import (
    Cliente, Equipo, OrdenReparacion, HistorialEstado,
    Repuesto, PerfilUsuario, ProductoTaller, ConsultaProducto
)
from .forms import (
    ClienteForm, EquipoForm, OrdenForm,
    CambioEstadoForm, RepuestoForm, LoginForm
)
from .utils import enviar_notificacion


def _get_tenant():
    """Retorna el taller (tenant) activo desde la conexion de BD."""
    return getattr(connection, 'tenant', None)


def _get_rol(request):
    return getattr(request, 'rol', None)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        usuario = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )            
        if usuario:
            login(request, usuario)
            return redirect('dashboard')
        messages.error(request, 'Credenciales incorrectas.')
    return render(request, 'taller/login.html', {'form': form})


# def logout_view(request):
#     logout(request)
#     return redirect('login')
def logout_view(request):
    """
    Cierra sesion y redirige siempre a la landing publica,
    sin importar desde que subdominio (taller) se cerro sesion.
    """
    logout(request)

    scheme = 'https' if not settings.DEBUG else 'http'
    port   = request.get_port()
    host   = 'localhost' if settings.DEBUG else 'OrdenTec.com'

    if (scheme == 'http'  and port == '80') or \
       (scheme == 'https' and port == '443'):
        url = f"{scheme}://{host}/"
    else:
        url = f"{scheme}://{host}:{port}/"

    return redirect(url)

@login_required
def dashboard(request):
    taller = _get_tenant()
    rol    = _get_rol(request)

    if not taller:
        return render(request, 'taller/sin_taller.html')
    
    ordenes = OrdenReparacion.objects.all()
    hoy     = timezone.now().date()

    stats = {
        'total_activas':    ordenes.exclude(estado__in=['entregado', 'cancelado']).count(),
        'recibidas_hoy':    ordenes.filter(fecha_ingreso__date=hoy).count(),
        'listas_retirar':   ordenes.filter(estado='listo').count(),
        'urgentes':         ordenes.filter(prioridad='urgente').exclude(estado__in=['entregado', 'cancelado']).count(),
        'total_clientes':   Cliente.objects.count(),
        'total_ordenes':    ordenes.count(),
    }

    ordenes_recientes = ordenes.select_related('cliente', 'equipo', 'tecnico')[:10]

    return render(request, 'taller/dashboard.html', {
        'taller': taller, 'rol': rol,
        'stats': stats, 'ordenes_recientes': ordenes_recientes,
    })

@login_required
def dashboard_foto(request):
    taller = _get_tenant()
    rol    = _get_rol(request)

    if not taller:
        return render(request, 'taller/sin_taller.html')

    ordenes = OrdenReparacion.objects.all()
    hoy     = timezone.now().date()

    stats = {
        'total_activas':    ordenes.exclude(estado__in=['entregado', 'cancelado']).count(),
        'recibidas_hoy':    ordenes.filter(fecha_ingreso__date=hoy).count(),
        'listas_retirar':   ordenes.filter(estado='listo').count(),
        'urgentes':         ordenes.filter(prioridad='urgente').exclude(estado__in=['entregado', 'cancelado']).count(),
        'total_clientes':   Cliente.objects.count(),
        'total_ordenes':    ordenes.count(),
    }

    ordenes_recientes = ordenes.select_related('cliente', 'equipo', 'tecnico')[:10]

    return render(request, 'taller/vistafoto.html', {
        'taller': taller, 'rol': rol,
        'stats': stats, 'ordenes_recientes': ordenes_recientes,
    })

# ── CLIENTES ──────────────────────────────────────────────────────────────────

@login_required
def lista_clientes(request):
    q = request.GET.get('q', '')
    clientes = Cliente.objects.all()
    if q:
        clientes = clientes.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) |
            Q(telefono__icontains=q) | Q(email__icontains=q)
        )
    clientes = clientes.annotate(num_ordenes=Count('ordenes'))
    return render(request, 'taller/clientes/lista.html', {
        'clientes': clientes, 'q': q,
        'taller': _get_tenant()
    })


@login_required
def crear_cliente(request):
    form = ClienteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cliente = form.save()
        messages.success(request, f'Cliente {cliente.nombre_completo()} registrado.')
        if request.GET.get('next') == 'orden':
            return redirect('crear_orden_cliente', cliente_id=cliente.id)
        return redirect('detalle_cliente', pk=cliente.id)
    return render(request, 'taller/clientes/form.html', {
        'form': form, 'titulo': 'Nuevo Cliente', 'taller': _get_tenant()
    })


@login_required
def detalle_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    return render(request, 'taller/clientes/detalle.html', {
        'cliente': cliente,
        'ordenes': cliente.ordenes.select_related('equipo').order_by('-creado_en'),
        'equipos': cliente.equipos.all(),
        'taller': _get_tenant()
    })


@login_required
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=cliente)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cliente actualizado.')
        return redirect('detalle_cliente', pk=cliente.id)
    return render(request, 'taller/clientes/form.html', {
        'form': form, 'titulo': f'Editar: {cliente.nombre_completo()}',
        'cliente': cliente, 'taller': _get_tenant()
    })


# ── EQUIPOS ───────────────────────────────────────────────────────────────────

@login_required
def crear_equipo(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    form = EquipoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        equipo = form.save(commit=False)
        equipo.cliente = cliente
        equipo.save()
        messages.success(request, f'Equipo {equipo} registrado.')

        # Si viene de la orden, redirigir con equipo_id para autoselección
        if request.GET.get('next') == 'orden':
            return redirect(
                f'/ordenes/nueva/cliente/{cliente.id}/?equipo_id={equipo.id}'
            )
        return redirect('detalle_cliente', pk=cliente.id)

    return render(request, 'taller/equipos/form.html', {
        'form':    form,
        'cliente': cliente,
        'titulo':  f'Nuevo equipo para {cliente.nombre_completo()}',
        'taller':  _get_tenant(),
    })

# @login_required
# def crear_equipo(request, cliente_id):
#     cliente = get_object_or_404(Cliente, pk=cliente_id)
#     form = EquipoForm(request.POST or None, request.FILES or None)
#     if request.method == 'POST' and form.is_valid():
#         equipo = form.save(commit=False)
#         equipo.cliente = cliente
#         equipo.save()
#         messages.success(request, f'Equipo {equipo} registrado.')
#         if request.GET.get('next') == 'orden':
#             return redirect('crear_orden_equipo', equipo_id=equipo.id)
#         return redirect('detalle_cliente', pk=cliente.id)
#     return render(request, 'taller/equipos/form.html', {
#         'form': form, 'cliente': cliente,
#         'titulo': f'Nuevo equipo para {cliente.nombre_completo()}',
#         'taller': _get_tenant()
#     })


# ── ÓRDENES ───────────────────────────────────────────────────────────────────

@login_required
def lista_ordenes(request):
    estado = request.GET.get('estado', '')
    q      = request.GET.get('q', '')
    ordenes = OrdenReparacion.objects.select_related('cliente', 'equipo', 'tecnico')
    if estado:
        ordenes = ordenes.filter(estado=estado)
    if q:
        ordenes = ordenes.filter(
            Q(numero__icontains=q) |
            Q(cliente__nombre__icontains=q) |
            Q(cliente__apellido__icontains=q) |
            Q(equipo__marca__icontains=q)
        )
    estados_count = {
        e: OrdenReparacion.objects.filter(estado=e).count()
        for e, _ in OrdenReparacion.ESTADO_CHOICES
    }
    hoy     = timezone.now().date()
    stats = {
        'total_activas':    ordenes.exclude(estado__in=['entregado', 'cancelado']).count(),
        'recibidas_hoy':    ordenes.filter(fecha_ingreso__date=hoy).count(),
        'listas_retirar':   ordenes.filter(estado='listo').count(),
        'urgentes':         ordenes.filter(prioridad='urgente').exclude(estado__in=['entregado', 'cancelado']).count(),
        'total_clientes':   Cliente.objects.count(),
        'total_ordenes':    ordenes.count(),
    }
    
    return render(request, 'taller/ordenes/lista.html', {
        'stats':stats,
        'ordenes': ordenes, 'estado_filtro': estado, 'q': q,
        'estados': OrdenReparacion.ESTADO_CHOICES,
        'estados_count': estados_count,
        'taller': _get_tenant(),
    })


@login_required
def crear_orden(request, cliente_id=None, equipo_id=None):
    cliente_inicial = get_object_or_404(Cliente, pk=cliente_id) if cliente_id else None
    equipo_inicial  = None
    if equipo_id:
        equipo_inicial  = get_object_or_404(Equipo, pk=equipo_id)
        cliente_inicial = equipo_inicial.cliente

    form = OrdenForm(
        request.POST or None,
        cliente_inicial=cliente_inicial,
        equipo_inicial=equipo_inicial
    )

    if request.method == 'POST' and form.is_valid():
        orden = form.save()
        HistorialEstado.objects.create(
            orden=orden, estado_nuevo='recibido',
            comentario='Orden creada. Equipo recibido en el taller.',
            usuario=request.user
        )
        enviar_notificacion(orden, 'recibido', request.user)
        messages.success(request, f'Orden {orden.numero} creada. Cliente notificado.')
        return redirect('detalle_orden', pk=orden.id)

    return render(request, 'taller/ordenes/form.html', {
        'form': form, 'titulo': 'Nueva Orden de Reparación',
        'taller': _get_tenant(), 'cliente_inicial': cliente_inicial,
    })


@login_required
def detalle_orden(request, pk):
    orden = get_object_or_404(
        OrdenReparacion.objects.select_related('cliente', 'equipo', 'tecnico'), pk=pk
    )
    repuestos = orden.repuestos.all()
    return render(request, 'taller/ordenes/detalle.html', {
        'orden': orden,
        'historial': orden.historial.select_related('usuario').all(),
        'repuestos': repuestos,
        'form_estado': CambioEstadoForm(instance=orden),
        'form_repuesto': RepuestoForm(),
        'total_repuestos': sum(r.subtotal for r in repuestos),
        'taller': _get_tenant(),
        'rol': _get_rol(request),
    })


@login_required
@require_POST
def cambiar_estado(request, pk):
    orden = get_object_or_404(OrdenReparacion, pk=pk)
    form  = CambioEstadoForm(request.POST, instance=orden)
    if form.is_valid():
        estado_anterior = orden.estado
        orden = form.save(commit=False)
        if orden.estado == 'listo'     and not orden.fecha_listo:
            orden.fecha_listo = timezone.now()
        if orden.estado == 'entregado' and not orden.fecha_entrega:
            orden.fecha_entrega = timezone.now()
        orden.save()
        h = HistorialEstado.objects.create(
            orden=orden, estado_anterior=estado_anterior,
            estado_nuevo=orden.estado,
            comentario=form.cleaned_data.get('comentario', ''),
            usuario=request.user
        )
        if estado_anterior != orden.estado:
            notificado = enviar_notificacion(orden, orden.estado, request.user)
            if notificado:
                h.notificado = True; h.save()
            messages.success(request, f'Estado actualizado a "{orden.get_estado_display()}".')
    return redirect('detalle_orden', pk=pk)


@login_required
@require_POST
def agregar_repuesto(request, pk):
    orden = get_object_or_404(OrdenReparacion, pk=pk)
    form  = RepuestoForm(request.POST)
    if form.is_valid():
        r = form.save(commit=False)
        r.orden = orden
        r.save()
        messages.success(request, 'Repuesto agregado.')
    return redirect('detalle_orden', pk=pk)


@login_required
def eliminar_repuesto(request, pk, repuesto_id):
    orden    = get_object_or_404(OrdenReparacion, pk=pk)
    repuesto = get_object_or_404(Repuesto, pk=repuesto_id, orden=orden)
    repuesto.delete()
    messages.success(request, 'Repuesto eliminado.')
    return redirect('detalle_orden', pk=pk)

@login_required
def guia_uso(request):
    """
    Pagina de ayuda fija dentro del panel del taller.
    Explica el flujo completo de uso del sistema.
    """
    return render(request, 'taller/guia.html', {
        'taller': _get_tenant(),
        'rol':    _get_rol(request),
    })
# ── SEGUIMIENTO PÚBLICO ───────────────────────────────────────────────────────

def seguimiento_orden(request, token):
    """
    Vista publica accesible sin login.
    Puede ser llamada desde el schema del taller o desde el schema publico.
    """
    orden = get_object_or_404(
        OrdenReparacion.objects.select_related('cliente', 'equipo'),
        token_seguimiento=token
    )
    historial = orden.historial.filter(
        estado_nuevo__in=[e for e, _ in OrdenReparacion.ESTADO_CHOICES
                          if e != 'cancelado']
    ).order_by('creado_en')
    taller = _get_tenant()
    return render(request, 'seguimiento/orden.html', {
        'orden': orden, 'historial': historial, 'taller': taller,
    })


# ── API ───────────────────────────────────────────────────────────────────────

@login_required
def api_equipos_cliente(request, cliente_id):
    equipos = Equipo.objects.filter(cliente_id=cliente_id).values(
        'id', 'marca', 'modelo', 'tipo', 'serial'
    )
    return JsonResponse({'equipos': list(equipos)})
