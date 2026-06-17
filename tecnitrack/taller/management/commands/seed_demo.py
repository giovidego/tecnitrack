"""
TecniTrack - Seed de datos de demo (schema-based tenancy)
Crea un tenant de prueba con su schema PostgreSQL y datos de ejemplo.
Uso: python manage.py seed_demo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random


class Command(BaseCommand):
    help = 'Crea datos de demostracion para TecniTrack (schema-based)'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creando tenant de demo...')

        # 1. Superusuario en schema publico
        from tenants.models import Taller, Dominio
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@tecnitrack.cl', 'admin123')
            self.stdout.write('  Superusuario: admin / admin123')

        # 2. Crear el tenant (schema de PostgreSQL)
        schema_name = 'demo_taller'
        if Taller.objects.filter(schema_name=schema_name).exists():
            taller = Taller.objects.get(schema_name=schema_name)
            self.stdout.write(f'  Tenant existente: {schema_name}')
        else:
            taller = Taller(
                schema_name=schema_name,
                nombre='Reparaciones Munoz',
                email='contacto@reparacionesmunoz.cl',
                telefono='+56 9 8765 4321',
                direccion='Av. Providencia 1234, Santiago',
                plan='profesional',
                activo=True,
                notif_email=True,
            )
            taller.save()  # Crea el schema en PostgreSQL
            self.stdout.write(f'  Schema creado: {schema_name}')

            # Dominio del taller
            if not Dominio.objects.filter(tenant=taller).exists():
                Dominio.objects.create(
                    domain='demo-taller.localhost',
                    tenant=taller,
                    is_primary=True
                )

        # 3. Poblar el schema del taller
        from django_tenants.utils import schema_context
        with schema_context(schema_name):
            self._poblar_schema(taller)

        self.stdout.write(self.style.SUCCESS(
            '\nDatos de demo creados!\n\n'
            '  Acceso al taller demo:\n'
            '  Host: demo-taller.localhost:8000\n'
            '  Usuario: dueno_taller / taller123\n'
            '  Tecnico: tecnico1 / taller123\n\n'
            '  Admin global: http://localhost:8000/admin/\n'
            '  Usuario: admin / admin123\n'
        ))

    def _poblar_schema(self, taller):
        from taller.models import (
            PerfilUsuario, Cliente, Equipo,
            OrdenReparacion, HistorialEstado, Suscripcion
        )

        # Usuarios del taller
        dueno    = self._crear_usuario('dueno_taller', 'Rodrigo', 'Munoz',     'dueno@taller.cl',  'taller123')
        tecnico1 = self._crear_usuario('tecnico1',     'Felipe',  'Soto',      'felipe@taller.cl', 'taller123')
        tecnico2 = self._crear_usuario('tecnico2',     'Valentina','Riquelme', 'vale@taller.cl',   'taller123')

        PerfilUsuario.objects.get_or_create(usuario=dueno,    defaults={'rol': 'dueno'})
        PerfilUsuario.objects.get_or_create(usuario=tecnico1, defaults={'rol': 'tecnico'})
        PerfilUsuario.objects.get_or_create(usuario=tecnico2, defaults={'rol': 'tecnico'})

        # Suscripcion trial
        if not Suscripcion.objects.exists():
            Suscripcion.objects.create(
                plan='profesional',
                estado='trial',
                inicio_trial=timezone.now() - timedelta(days=10),
                fin_trial=timezone.now() + timedelta(days=20),
            )

        # Clientes
        clientes_data = [
            ('Juan',    'Perez',     '12.345.678-9', 'juan.perez@gmail.com',  '+56 9 1111 2222'),
            ('Maria',   'Gonzalez',  '9.876.543-2',  'maria.g@hotmail.com',   '+56 9 3333 4444'),
            ('Carlos',  'Rodriguez', '15.432.109-8', 'carlos.r@yahoo.com',    '+56 9 5555 6666'),
            ('Ana',     'Martinez',  '11.222.333-4', 'ana.m@gmail.com',       '+56 9 7777 8888'),
            ('Pedro',   'Lopez',     '8.765.432-1',  '',                       '+56 9 9999 0000'),
        ]
        clientes = []
        for nombre, apellido, rut, email, tel in clientes_data:
            c, _ = Cliente.objects.get_or_create(
                rut=rut,
                defaults={'nombre': nombre, 'apellido': apellido, 'email': email, 'telefono': tel}
            )
            clientes.append(c)

        # Equipos
        equipos_data = [
            (clientes[0], 'notebook',  'HP',          'Pavilion 15',      'SN-HP-001'),
            (clientes[0], 'notebook',  'Lenovo',      'ThinkPad T14',     'SN-LN-002'),
            (clientes[1], 'notebook',  'Dell',        'Inspiron 15',      'SN-DL-003'),
            (clientes[2], 'desktop',   'Ensamblado',  'PC Gamer Custom',  ''),
            (clientes[3], 'notebook',  'Apple',       'MacBook Pro 2020', 'C02ZG1XVMD6T'),
            (clientes[4], 'impresora', 'HP',          'LaserJet Pro M404','SN-HP-LJ-005'),
        ]
        equipos = []
        for cliente, tipo, marca, modelo, serial in equipos_data:
            e, _ = Equipo.objects.get_or_create(
                cliente=cliente, marca=marca, modelo=modelo,
                defaults={'tipo': tipo, 'serial': serial}
            )
            equipos.append(e)

        # Ordenes con distintos estados
        ordenes_data = [
            (clientes[0], equipos[0], tecnico1, 'recibido',         'normal', 'La pantalla parpadea y se apaga sola', 0),
            (clientes[0], equipos[1], tecnico2, 'diagnostico',      'alta',   'No enciende. Se escucha un click al prender.', -2),
            (clientes[1], equipos[2], tecnico1, 'en_reparacion',   'normal', 'Teclado con varias teclas que no responden', -5),
            (clientes[2], equipos[3], tecnico2, 'espera_repuestos', 'urgente','PC no inicia Windows, disco con sectores danados', -7),
            (clientes[3], equipos[4], tecnico1, 'listo',            'alta',   'Bateria se agota en menos de 1 hora', -10),
            (clientes[4], equipos[5], None,     'entregado',        'normal', 'Impresora no conecta por WiFi', -15),
        ]

        for cliente, equipo, tecnico, estado, prioridad, problema, dias_atras in ordenes_data:
            if OrdenReparacion.objects.filter(cliente=cliente, equipo=equipo).exists():
                continue
            fecha = timezone.now() + timedelta(days=dias_atras)
            orden = OrdenReparacion.objects.create(
                cliente=cliente, equipo=equipo, tecnico=tecnico,
                estado=estado, prioridad=prioridad,
                problema_reportado=problema, fecha_ingreso=fecha,
                presupuesto=random.choice([25000, 45000, 80000, 120000, None]),
            )
            HistorialEstado.objects.create(
                orden=orden, estado_nuevo='recibido',
                comentario='Equipo recibido.', usuario=dueno, notificado=True
            )
            if estado != 'recibido':
                HistorialEstado.objects.create(
                    orden=orden, estado_anterior='recibido', estado_nuevo=estado,
                    comentario=f'Estado actualizado a {orden.get_estado_display()}.',
                    usuario=tecnico or dueno, notificado=True
                )

        self.stdout.write(f'  Schema {taller.schema_name}: 3 usuarios, 5 clientes, 6 equipos, 6 ordenes')

    def _crear_usuario(self, username, nombre, apellido, email, password):
        if not User.objects.filter(username=username).exists():
            return User.objects.create_user(
                username=username, email=email, password=password,
                first_name=nombre, last_name=apellido
            )
        return User.objects.get(username=username)
