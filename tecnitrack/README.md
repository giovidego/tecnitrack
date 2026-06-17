# TecniTrack — SaaS con Schema-Based Multi-Tenancy

## Arquitectura

Cada taller tiene su propio schema de PostgreSQL. El aislamiento es físico.

```
PostgreSQL
├── schema: public          ← Taller (tenant), Dominio, User global, Admin
├── schema: demo_taller     ← Cliente, Equipo, OrdenReparacion, PerfilUsuario...
├── schema: taller_perez    ← Cliente, Equipo, OrdenReparacion, PerfilUsuario...
└── schema: servicio_norte  ← Cliente, Equipo, OrdenReparacion, PerfilUsuario...
```

## Requisitos previos

- **Python 3.11+**
- **PostgreSQL 14+** (obligatorio — django-tenants no funciona con SQLite)

## Instalación

```bash
# 1. Clonar y entrar al directorio
cd tecnitrack

# 2. Entorno virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con los datos de tu PostgreSQL

# 5. Crear la base de datos en PostgreSQL
psql -U postgres -c "CREATE DATABASE tecnitrack;"

# 6. Aplicar migraciones del schema público
python manage.py migrate_schemas --shared

# 7. Aplicar migraciones de los tenants
python manage.py migrate_schemas --tenant

# 8. Cargar datos de demo
python manage.py seed_demo

# 9. Ejecutar servidor
python manage.py runserver
```

## Acceso

| Entorno | URL | Usuario | Contraseña |
|---------|-----|---------|------------|
| Admin global | http://localhost:8000/admin/ | admin | admin123 |
| Taller demo | http://demo-taller.localhost:8000/ | dueno_taller | taller123 |
| Taller demo | http://demo-taller.localhost:8000/ | tecnico1 | taller123 |

> Para desarrollo local, agregar al archivo `/etc/hosts` (Linux/Mac) o
> `C:\Windows\System32\drivers\etc\hosts` (Windows):
> ```
> 127.0.0.1 demo-taller.localhost
> ```

## Comandos clave de django-tenants

```bash
# Migrar solo schema publico
python manage.py migrate_schemas --shared

# Migrar todos los tenants
python manage.py migrate_schemas --tenant

# Migrar un tenant especifico
python manage.py migrate_schemas --schema=demo_taller

# Ejecutar comando dentro de un schema especifico
python manage.py tenant_command shell --schema=demo_taller

# Listar todos los tenants
python manage.py shell -c "from tenants.models import Taller; print(Taller.objects.all())"
```

## Estructura del proyecto

```
tecnitrack/
├── tenants/                    # App schema publico
│   ├── models.py               # Taller(TenantMixin), Dominio(DomainMixin)
│   └── admin.py
├── taller/                     # App replicada en cada schema de tenant
│   ├── models.py               # Cliente, Equipo, Orden, Tienda, Suscripcion
│   ├── views.py                # Dashboard, clientes, ordenes (sin FK taller)
│   ├── views_onboarding.py     # Crea schemas nuevos con schema_context()
│   ├── views_suscripcion.py
│   ├── middleware.py           # PerfilMiddleware
│   ├── middleware_suscripcion.py
│   ├── urls.py                 # Rutas privadas del tenant
│   └── urls_public.py          # Landing, registro, seguimiento publico
└── tecnitrack/
    ├── settings.py             # SHARED_APPS, TENANT_APPS, DATABASE_ROUTERS
    ├── urls.py                 # ROOT_URLCONF (tenant)
    └── urls_public.py          # PUBLIC_SCHEMA_URLCONF
```

## Diferencias clave vs FK discriminator

| Aspecto | FK discriminator (anterior) | Schema por tenant (actual) |
|---------|---------------------------|---------------------------|
| Aislamiento | Logico (WHERE taller_id=X) | Fisico (schema separado) |
| Seguridad | Bug puede filtrar datos | Imposible cruzar datos |
| Backup | Solo total | Por taller independiente |
| Queries | Necesitan filtro FK | Sin filtro — scope automatico |
| BD requerida | SQLite o PostgreSQL | Solo PostgreSQL |
