"""
OrdenTec - App Tenants (schema público)
Cada Taller es un tenant con su propio schema de PostgreSQL.
Este modelo vive en el schema 'public' y es gestionado por django-tenants.
"""
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Taller(TenantMixin):
    """
    Tenant principal. django-tenants crea automáticamente un schema
    de PostgreSQL por cada instancia de este modelo.

    Campos heredados de TenantMixin:
        schema_name  (str, unique) — nombre del schema en PostgreSQL
        created_on   (date)
    """
    PLAN_CHOICES = [
        ('basico', 'Básico'),
        ('profesional', 'Profesional'),
        ('ilimitado', 'Ilimitado'),
    ]

    nombre       = models.CharField(max_length=120)
    rut          = models.CharField(max_length=12, blank=True)
    telefono     = models.CharField(max_length=20, blank=True)
    email        = models.EmailField(unique=True)
    direccion    = models.CharField(max_length=200, blank=True)
    plan         = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basico')
    activo       = models.BooleanField(default=True)

    # Configuración de notificaciones
    notif_email        = models.BooleanField(default=True)
    mensaje_bienvenida = models.TextField(
        blank=True,
        default="Hemos recibido tu equipo. Te notificaremos en cada etapa de la reparación."
    )

    # django-tenants: crear el schema automáticamente al guardar
    auto_create_schema = True
    auto_drop_schema   = False   # seguridad: no borrar datos por accidente

    class Meta:
        verbose_name = "Taller (Tenant)"
        verbose_name_plural = "Talleres (Tenants)"

    def __str__(self):
        return f"{self.nombre} [{self.schema_name}]"

    def get_plan_info(self):
        from django.conf import settings
        return settings.PLANES.get(self.plan, {})


class Dominio(DomainMixin):
    """
    Dominio o subdominio asociado a un taller.
    Ejemplos:
        reparaciones-munoz.OrdenTec.com  → taller Reparaciones Muñoz
        localhost                         → desarrollo local

    django-tenants usa este modelo para rutear cada request
    al schema correcto según el Host header.
    """
    class Meta:
        verbose_name = "Dominio"
        verbose_name_plural = "Dominios"

    def __str__(self):
        return f"{self.domain} → {self.tenant.nombre}"
