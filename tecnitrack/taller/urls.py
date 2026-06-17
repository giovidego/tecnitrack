"""URLs privadas del taller (schema del tenant)"""
from django.urls import path
from . import views
from . import views_onboarding as onb
from . import views_suscripcion as sus

urlpatterns = [
    # Auth (tambien disponible en schema del tenant)
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('auth/token/<str:token>/', onb.consumir_token_login, name='consumir_token'),
    # Dashboard
    path('',          views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Clientes
    path('clientes/',                      views.lista_clientes,  name='lista_clientes'),
    path('clientes/nuevo/',                views.crear_cliente,   name='crear_cliente'),
    path('clientes/<int:pk>/',             views.detalle_cliente, name='detalle_cliente'),
    path('clientes/<int:pk>/editar/',      views.editar_cliente,  name='editar_cliente'),
    path('clientes/<int:cliente_id>/equipos/nuevo/', views.crear_equipo, name='crear_equipo'),

    # Ordenes
    path('ordenes/',                                    views.lista_ordenes,      name='lista_ordenes'),
    path('ordenes/nueva/',                              views.crear_orden,        name='crear_orden'),
    path('ordenes/nueva/cliente/<int:cliente_id>/',     views.crear_orden,        name='crear_orden_cliente'),
    path('ordenes/nueva/equipo/<int:equipo_id>/',       views.crear_orden,        name='crear_orden_equipo'),
    path('ordenes/<int:pk>/',                           views.detalle_orden,      name='detalle_orden'),
    path('ordenes/<int:pk>/estado/',                    views.cambiar_estado,     name='cambiar_estado'),
    path('ordenes/<int:pk>/repuestos/agregar/',         views.agregar_repuesto,   name='agregar_repuesto'),
    path('ordenes/<int:pk>/repuestos/<int:repuesto_id>/eliminar/', views.eliminar_repuesto, name='eliminar_repuesto'),

    # Equipo interno / invitaciones
    path('equipo/invitar/', onb.invitar_tecnico, name='invitar_tecnico'),

    # Suscripcion
    path('suscripcion/vencida/', sus.suscripcion_vencida, name='suscripcion_vencida'),
    path('planes/',              sus.ver_planes,           name='ver_planes'),

    # Seguimiento publico (tambien accesible desde schema del taller)
    path('seguimiento/<uuid:token>/', views.seguimiento_orden, name='seguimiento_orden'),

    # API
    path('api/clientes/<int:cliente_id>/equipos/', views.api_equipos_cliente, name='api_equipos_cliente'),
]
