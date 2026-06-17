"""
TecniTrack - Admin del schema privado del taller
"""
from django.contrib import admin
from .models import (
    PerfilUsuario, Cliente, Equipo, OrdenReparacion,
    HistorialEstado, Repuesto, ProductoTaller, ConsultaProducto,
    Suscripcion, InvitacionTecnico
)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'rol', 'activo']
    list_filter  = ['rol', 'activo']


class RepuestoInline(admin.TabularInline):
    model = Repuesto
    extra = 0


class HistorialInline(admin.TabularInline):
    model  = HistorialEstado
    extra  = 0
    readonly_fields = ['creado_en']


@admin.register(OrdenReparacion)
class OrdenAdmin(admin.ModelAdmin):
    list_display   = ['numero', 'cliente', 'equipo', 'estado', 'prioridad', 'tecnico', 'fecha_ingreso']
    list_filter    = ['estado', 'prioridad']
    search_fields  = ['numero', 'cliente__nombre', 'equipo__marca']
    readonly_fields = ['numero', 'token_seguimiento', 'creado_en']
    inlines        = [RepuestoInline, HistorialInline]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display  = ['nombre_completo', 'telefono', 'email']
    search_fields = ['nombre', 'apellido', 'rut', 'email', 'telefono']


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display  = ['marca', 'modelo', 'tipo', 'cliente', 'serial']
    list_filter   = ['tipo', 'marca']
    search_fields = ['marca', 'modelo', 'serial', 'cliente__nombre']


@admin.register(ProductoTaller)
class ProductoAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'categoria', 'precio', 'stock', 'activo']
    list_filter   = ['categoria', 'activo']
    search_fields = ['nombre']


@admin.register(ConsultaProducto)
class ConsultaAdmin(admin.ModelAdmin):
    list_display  = ['nombre_cliente', 'producto', 'email', 'leida', 'creado_en']
    list_filter   = ['leida']
    readonly_fields = ['creado_en']


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display    = ['plan', 'estado', 'dias_trial_restantes', 'fin_trial']
    readonly_fields = ['creado_en', 'actualizado_en']


@admin.register(InvitacionTecnico)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ['email', 'rol', 'usada', 'creada_en', 'expira_en']
    list_filter  = ['usada', 'rol']
