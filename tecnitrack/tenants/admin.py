from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
from .models import Taller, Dominio


class DominioInline(admin.TabularInline):
    model = Dominio
    extra = 1


@admin.register(Taller)
class TallerAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display  = ['nombre', 'schema_name', 'plan', 'activo', 'email']
    list_filter   = ['plan', 'activo']
    search_fields = ['nombre', 'schema_name', 'email']
    inlines       = [DominioInline]


@admin.register(Dominio)
class DominioAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tenant', 'is_primary']
