#!/bin/bash
# TecniTrack - Script de instalación rápida
# Ejecutar con: bash instalar.sh

set -e

echo "======================================"
echo "  TecniTrack - Instalación rápida"
echo "======================================"
echo ""

# 1. Crear entorno virtual
echo "→ Creando entorno virtual..."
python3 -m venv venv

# 2. Activar
source venv/bin/activate

# 3. Instalar dependencias
echo "→ Instalando dependencias..."
pip install --upgrade pip -q
pip install django pillow gunicorn whitenoise -q

# 4. Migrar base de datos
echo "→ Aplicando migraciones..."
python manage.py migrate

# 5. Cargar datos de demo
echo "→ Cargando datos de demostración..."
python manage.py seed_demo

echo ""
echo "======================================"
echo "  ✅ Instalación completa"
echo "======================================"
echo ""
echo "  Iniciar servidor:"
echo "  source venv/bin/activate"
echo "  python manage.py runserver"
echo ""
echo "  Abrir: http://localhost:8000"
echo ""
echo "  Credenciales:"
echo "  → dueno_taller / taller123"
echo "  → tecnico1 / taller123"
echo "  → admin / admin123"
echo ""
