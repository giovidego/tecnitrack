"""
TecniTrack - URLs publicas (schema public): landing, registro, seguimiento
"""
from django.urls import path
from . import views_onboarding as onb
from . import views

urlpatterns = [
    # Landing publica
    path('', onb.landing, name='landing'),

    # Registro SaaS y onboarding
    path('registro/', onb.registro_taller, name='registro_taller'),
    path('registro/enviado/<str:email>/', onb.registro_confirmacion_enviada, name='registro_confirmacion_enviada'),
    path('registro/confirmar/<str:token>/', onb.confirmar_email, name='confirmar_email'),
    path('registro/configurar/<int:paso>/', onb.onboarding_wizard, name='onboarding_wizard'),
    path('registro/listo/', onb.onboarding_completado, name='onboarding_completado'),

    # Invitacion de tecnicos (link enviado por email, accesible publicamente)
    path('invitacion/<uuid:token>/', onb.aceptar_invitacion, name='aceptar_invitacion'),

    # Seguimiento publico de ordenes (accede por token UUID, sin login)
    path('seguimiento/<uuid:token>/', views.seguimiento_orden, name='seguimiento_orden'),

    # Login / logout (disponibles en ambos contextos)
    path('login/',     onb.login_publico,    name='login_publico'),
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
]
