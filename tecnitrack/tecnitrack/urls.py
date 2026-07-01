"""
OrdenTec - URLs privadas por tenant (dashboard, ordenes, clientes, tienda)
django-tenants las enruta segun el schema activo del request.
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('taller.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
