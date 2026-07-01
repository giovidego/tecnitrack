"""
OrdenTec - Modelos de Onboarding y Suscripción
Añadir a taller/models.py o importar desde aquí
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class InvitacionTaller(models.Model):
    """
    Invitación para que un técnico se una a un taller existente.
    El dueño genera el link y lo comparte.
    """
    taller = models.ForeignKey('Taller', on_delete=models.CASCADE, related_name='invitaciones')
    email = models.EmailField()
    rol = models.CharField(max_length=20, default='tecnico')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    usada = models.BooleanField(default=False)
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.expira_en:
            self.expira_en = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def vigente(self):
        return not self.usada and timezone.now() < self.expira_en

    def __str__(self):
        return f"Invitación {self.email} → {self.taller.nombre}"

    class Meta:
        verbose_name = "Invitación"
        verbose_name_plural = "Invitaciones"


class RegistroTaller(models.Model):
    """
    Formulario de registro inicial de un taller.
    Se completa ANTES de crear el usuario/taller.
    Permite seguimiento de leads que no completaron el proceso.
    """
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de confirmar email'),
        ('confirmado', 'Email confirmado'),
        ('completado', 'Onboarding completo'),
        ('expirado', 'Expirado'),
    ]

    # Datos del taller
    nombre_taller = models.CharField(max_length=120)
    nombre_dueno = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20)
    ciudad = models.CharField(max_length=80, blank=True)

    # Control del proceso
    token_confirmacion = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    plan_elegido = models.CharField(max_length=20, default='basico')

    # Referencia al taller creado (cuando completa onboarding)
    taller_creado = models.OneToOneField(
        'Taller', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='registro_origen'
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    confirmado_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nombre_taller} ({self.email}) - {self.get_estado_display()}"

    class Meta:
        verbose_name = "Registro de Taller"
        verbose_name_plural = "Registros de Talleres"
        ordering = ['-creado_en']


class Suscripcion(models.Model):
    """
    Suscripción activa de un taller al servicio SaaS.
    Controla el período de prueba y el plan activo.
    """
    ESTADO_CHOICES = [
        ('trial', 'Período de prueba'),
        ('activa', 'Activa'),
        ('vencida', 'Vencida'),
        ('cancelada', 'Cancelada'),
    ]

    taller = models.OneToOneField('Taller', on_delete=models.CASCADE, related_name='suscripcion')
    plan = models.CharField(max_length=20, default='basico')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='trial')

    # Fechas
    inicio_trial = models.DateTimeField(default=timezone.now)
    fin_trial = models.DateTimeField()
    inicio_pago = models.DateTimeField(null=True, blank=True)
    proximo_cobro = models.DateField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)

    # Métricas de uso
    ordenes_este_mes = models.PositiveIntegerField(default=0)
    mes_conteo = models.DateField(default=timezone.now)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.fin_trial:
            self.fin_trial = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def dias_trial_restantes(self):
        if self.estado != 'trial':
            return 0
        delta = self.fin_trial - timezone.now()
        return max(0, delta.days)

    @property
    def trial_activo(self):
        return self.estado == 'trial' and timezone.now() < self.fin_trial

    @property
    def acceso_permitido(self):
        return self.estado in ('trial', 'activa') and (
            self.estado != 'trial' or self.trial_activo
        )

    def __str__(self):
        return f"{self.taller.nombre} — {self.get_estado_display()} ({self.plan})"

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"
