"""
OrdenTec - Modelos del taller (schema privado por tenant)
Con django-tenants cada taller tiene su propio schema de PostgreSQL.
NO necesitan FK a Taller — el aislamiento lo garantiza el schema.
"""
import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.db import connection
from tenants.models import Dominio


class PerfilUsuario(models.Model):
    ROL_CHOICES = [
        ('dueno',   'Dueño'),
        ('admin',   'Administrador'),
        ('tecnico', 'Técnico'),
    ]
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol     = models.CharField(max_length=20, choices=ROL_CHOICES, default='tecnico')
    activo  = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuario"

    def __str__(self):
        return f"{self.usuario.get_full_name()} ({self.get_rol_display()})"


class Cliente(models.Model):
    nombre       = models.CharField(max_length=120)
    apellido     = models.CharField(max_length=120, blank=True)
    rut          = models.CharField(max_length=12, blank=True)
    email        = models.EmailField(blank=True)
    telefono     = models.CharField(max_length=20)
    direccion    = models.CharField(max_length=200, blank=True)
    notas        = models.TextField(blank=True)
    creado_en    = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip()

    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    def ordenes_activas(self):
        return self.ordenes.exclude(estado__in=['entregado', 'cancelado']).count()

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-creado_en']


class Equipo(models.Model):
    TIPO_CHOICES = [
        ('notebook',  'Notebook'),
        ('desktop',   'PC de escritorio'),
        ('tablet',    'Tablet'),
        ('impresora', 'Impresora'),
        ('servidor',  'Servidor'),
        ('otro',      'Otro'),
    ]
    cliente     = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='equipos')
    tipo        = models.CharField(max_length=30, choices=TIPO_CHOICES, default='notebook')
    marca       = models.CharField(max_length=60)
    modelo      = models.CharField(max_length=100, blank=True)
    serial      = models.CharField(max_length=100, blank=True, verbose_name="N° Serie")
    descripcion = models.TextField(blank=True)
    foto        = models.ImageField(upload_to='equipos/', null=True, blank=True)
    creado_en   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} {self.marca} {self.modelo} ({self.cliente})"

    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        ordering = ['-creado_en']


class OrdenReparacion(models.Model):
    ESTADO_CHOICES = [
        ('recibido',         'Recibido'),
        ('diagnostico',      'En Diagnóstico'),
        ('espera_repuestos', 'Esperando Repuestos'),
        ('en_reparacion',   'En Reparación'),
        ('listo',            'Listo para Retirar'),
        ('entregado',        'Entregado'),
        ('cancelado',        'Cancelado'),
    ]
    PRIORIDAD_CHOICES = [
        ('baja',    'Baja'),
        ('normal',  'Normal'),
        ('alta',    'Alta'),
        ('urgente', 'Urgente'),
    ]

    numero             = models.CharField(max_length=20, unique=True, editable=False)
    token_seguimiento  = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cliente  = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='ordenes')
    equipo   = models.ForeignKey(Equipo,  on_delete=models.CASCADE, related_name='ordenes')
    tecnico  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_asignadas'
    )
    problema_reportado   = models.TextField()
    diagnostico          = models.TextField(blank=True)
    solucion_aplicada    = models.TextField(blank=True)
    accesorios_recibidos = models.CharField(max_length=300, blank=True)
    estado    = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='recibido')
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default='normal')
    presupuesto          = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    presupuesto_aprobado = models.BooleanField(null=True, blank=True)
    costo_final          = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    fecha_ingreso   = models.DateTimeField(default=timezone.now)
    fecha_estimada  = models.DateField(null=True, blank=True)
    fecha_listo     = models.DateTimeField(null=True, blank=True)
    fecha_entrega   = models.DateTimeField(null=True, blank=True)
    notas_internas  = models.TextField(blank=True)
    creado_en       = models.DateTimeField(auto_now_add=True)
    actualizado_en  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        super().save(*args, **kwargs)

    def _generar_numero(self):
        year   = timezone.now().year
        ultimo = OrdenReparacion.objects.filter(creado_en__year=year).count()
        return f"TK-{year}-{str(ultimo + 1).zfill(4)}"

    # def get_url_seguimiento(self):
    #     return f"{settings.SITE_URL}/seguimiento/{self.token_seguimiento}/"
    def get_url_seguimiento(self):
        dominio = Dominio.objects.filter(
            tenant__schema_name=connection.schema_name
        ).first()

        if dominio:
            protocolo = "https" if not settings.DEBUG else "http"
            return f"{protocolo}://{dominio.domain}:8000/seguimiento/{self.token_seguimiento}/"

        return f"{settings.SITE_URL}/seguimiento/{self.token_seguimiento}/"

    def get_estado_display_clase(self):
        return {'recibido':'secondary','diagnostico':'info','espera_repuestos':'warning',
                'en_reparacion':'primary','listo':'success','entregado':'dark','cancelado':'danger'}.get(self.estado,'secondary')

    def get_prioridad_clase(self):
        return {'baja':'secondary','normal':'info','alta':'warning','urgente':'danger'}.get(self.prioridad,'secondary')

    def dias_en_taller(self):
        fin = self.fecha_entrega or timezone.now()
        return (fin - self.fecha_ingreso).days

    def __str__(self):
        return f"Orden {self.numero} - {self.cliente} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Orden de Reparacion"
        verbose_name_plural = "Ordenes de Reparacion"
        ordering = ['-creado_en']


class HistorialEstado(models.Model):
    orden           = models.ForeignKey(OrdenReparacion, on_delete=models.CASCADE, related_name='historial')
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo    = models.CharField(max_length=30)
    comentario      = models.TextField(blank=True)
    usuario         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notificado      = models.BooleanField(default=False)
    creado_en       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.orden.numero}: {self.estado_anterior} -> {self.estado_nuevo}"

    class Meta:
        ordering = ['-creado_en']


class Repuesto(models.Model):
    orden           = models.ForeignKey(OrdenReparacion, on_delete=models.CASCADE, related_name='repuestos')
    descripcion     = models.CharField(max_length=200)
    cantidad        = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=0)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.descripcion} x{self.cantidad}"


class ProductoTaller(models.Model):
    CATEGORIA_CHOICES = [
        ('repuesto',        'Repuesto / Accesorio'),
        ('servicio',        'Servicio a precio fijo'),
        ('reacondicionado', 'Equipo reacondicionado'),
    ]
    nombre      = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    categoria   = models.CharField(max_length=30, choices=CATEGORIA_CHOICES, default='repuesto')
    precio      = models.DecimalField(max_digits=10, decimal_places=0)
    stock       = models.PositiveIntegerField(null=True, blank=True)
    foto        = models.ImageField(upload_to='tienda/', null=True, blank=True)
    activo      = models.BooleanField(default=True)
    creado_en   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} (${self.precio})"

    class Meta:
        verbose_name = "Producto de la Tienda"
        verbose_name_plural = "Productos de la Tienda"
        ordering = ['categoria', 'nombre']


class ConsultaProducto(models.Model):
    producto       = models.ForeignKey(ProductoTaller, on_delete=models.CASCADE, related_name='consultas')
    nombre_cliente = models.CharField(max_length=120)
    email          = models.EmailField()
    telefono       = models.CharField(max_length=20, blank=True)
    mensaje        = models.TextField()
    leida          = models.BooleanField(default=False)
    creado_en      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Consulta de {self.nombre_cliente} sobre {self.producto.nombre}"

    class Meta:
        ordering = ['-creado_en']


class Suscripcion(models.Model):
    ESTADO_CHOICES = [
        ('trial',     'Periodo de prueba'),
        ('activa',    'Activa'),
        ('vencida',   'Vencida'),
        ('cancelada', 'Cancelada'),
    ]
    plan              = models.CharField(max_length=20, default='basico')
    estado            = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='trial')
    inicio_trial      = models.DateTimeField(default=timezone.now)
    fin_trial         = models.DateTimeField(null=True, blank=True)
    inicio_pago       = models.DateTimeField(null=True, blank=True)
    proximo_cobro     = models.DateField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    ordenes_este_mes  = models.PositiveIntegerField(default=0)
    mes_conteo        = models.DateField(default=timezone.now)
    creado_en         = models.DateTimeField(auto_now_add=True)
    actualizado_en    = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.fin_trial:
            self.fin_trial = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def dias_trial_restantes(self):
        if self.estado != 'trial':
            return 0
        return max(0, (self.fin_trial - timezone.now()).days)

    @property
    def trial_activo(self):
        return self.estado == 'trial' and timezone.now() < self.fin_trial

    @property
    def acceso_permitido(self):
        return self.estado in ('trial', 'activa') and (
            self.estado != 'trial' or self.trial_activo
        )

    class Meta:
        verbose_name = "Suscripcion"


class InvitacionTecnico(models.Model):
    email      = models.EmailField()
    rol        = models.CharField(max_length=20, default='tecnico')
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    usada      = models.BooleanField(default=False)
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creada_en  = models.DateTimeField(auto_now_add=True)
    expira_en  = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.expira_en:
            self.expira_en = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def vigente(self):
        return not self.usada and timezone.now() < self.expira_en

    def __str__(self):
        return f"Invitacion -> {self.email}"
