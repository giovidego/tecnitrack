"""
TecniTrack - Settings con django-tenants (schema-based multi-tenancy)
Requiere PostgreSQL.
"""
import os
from pathlib import Path



BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY    = os.environ.get('SECRET_KEY', 'django-insecure-cambiar-en-produccion')
DEBUG         = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,.localhost',).split(',')

# ── APPS ──────────────────────────────────────────────────────────────────────
SHARED_APPS = [
    'django_tenants',
    'tenants',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
]

TENANT_APPS = [
    'taller',
    
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TENANT_MODEL        = 'tenants.Taller'
TENANT_DOMAIN_MODEL = 'tenants.Dominio'
PUBLIC_SCHEMA_NAME  = 'public'

# ── MIDDLEWARE ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'taller.middleware.PerfilMiddleware',
    'taller.middleware_suscripcion.SuscripcionMiddleware',
]

ROOT_URLCONF          = 'tecnitrack.urls'
PUBLIC_SCHEMA_URLCONF = 'tecnitrack.urls_public'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'taller.context_processors.tenant_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'tecnitrack.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE':   'django_tenants.postgresql_backend',
        'NAME':     os.environ.get('DB_NAME',     'tecnitrack'),
        'USER':     os.environ.get('DB_USER',     'tecnitrack_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'dev_password_123'),
        'HOST':     os.environ.get('DB_HOST',     'localhost'),
        'PORT':     os.environ.get('DB_PORT',     '5432'),
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

LANGUAGE_CODE = 'es-cl'
TIME_ZONE     = 'America/Santiago'
USE_I18N      = True
USE_TZ        = True

STATIC_URL       = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT      = BASE_DIR / 'staticfiles'
MEDIA_URL        = '/media/'
MEDIA_ROOT       = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND      = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'TecniTrack <noreply@tecnitrack.cl>'

SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')

SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}

PLANES = {
    'basico': {
        'nombre': 'Basico',
        'precio': 15000,
        'max_tecnicos': 2,
        'max_ordenes_mes': 50,
        'tienda_virtual': False,
    },
    'profesional': {
        'nombre': 'Profesional',
        'precio': 35000,
        'max_tecnicos': 5,
        'max_ordenes_mes': 200,
        'tienda_virtual': True,
    },
    'ilimitado': {
        'nombre': 'Ilimitado',
        'precio': 65000,
        'max_tecnicos': None,
        'max_ordenes_mes': None,
        'tienda_virtual': True,
    },
}
