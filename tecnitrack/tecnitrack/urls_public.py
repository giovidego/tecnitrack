"""
TecniTrack - URLs del schema público
Estas rutas responden cuando el dominio es el raíz (tecnitrack.cl)
o cuando se accede desde el schema 'public'.
Incluye: landing, registro de talleres, confirmación email, seguimiento público.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Panel de administración (solo en schema público)
    path('admin/', admin.site.urls),
    # Landing page, registro SaaS y onboarding
    path('', include('taller.urls_public')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
