"""
TecniTrack - Forms de Onboarding (schema-based tenancy)
"""
from django import forms
from django.contrib.auth.models import User
import re

CIUDADES_CL = [
    ('', 'Selecciona tu ciudad'),
    ('Santiago', 'Santiago'), ('Valparaiso', 'Valparaiso'),
    ('Concepcion', 'Concepcion'), ('La Serena', 'La Serena'),
    ('Antofagasta', 'Antofagasta'), ('Temuco', 'Temuco'),
    ('Rancagua', 'Rancagua'), ('Talca', 'Talca'),
    ('Iquique', 'Iquique'), ('Puerto Montt', 'Puerto Montt'),
    ('Arica', 'Arica'), ('Otra', 'Otra ciudad'),
]


class RegistroTallerForm(forms.Form):
    nombre_taller = forms.CharField(
        label='Nombre de tu taller', max_length=120,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg',
                                      'placeholder': 'Reparaciones Perez', 'autofocus': True})
    )
    nombre_dueno = forms.CharField(
        label='Tu nombre completo', max_length=120,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Juan Perez'})
    )
    email = forms.EmailField(
        label='Tu correo electronico',
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'juan@miempresa.cl'})
    )
    telefono = forms.CharField(
        label='Telefono de contacto', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': '+56 9 1234 5678'})
    )
    ciudad = forms.ChoiceField(
        label='Ciudad', choices=CIUDADES_CL,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    plan_elegido = forms.ChoiceField(
        choices=[('basico','Basico'),('profesional','Profesional'),('ilimitado','Ilimitado')],
        initial='profesional',
        widget=forms.HiddenInput()
    )
    acepta_terminos = forms.BooleanField(
        label='Acepto los terminos de uso',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        from tenants.models import Taller
        if Taller.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo electronico.')
        return email

    def clean_nombre_taller(self):
        nombre = self.cleaned_data['nombre_taller'].strip()
        if len(nombre) < 3:
            raise forms.ValidationError('El nombre debe tener al menos 3 caracteres.')
        return nombre


class WizardPaso2Form(forms.Form):
    username = forms.CharField(
        label='Nombre de usuario', max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg',
                                      'placeholder': 'juan_perez'}),
        help_text='Solo letras, numeros y guiones bajos.'
    )
    password1 = forms.CharField(
        label='Contrasena', min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'placeholder': '••••••••'})
    )
    password2 = forms.CharField(
        label='Confirmar contrasena',
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'placeholder': '••••••••'})
    )

    def clean_username(self):
        username = self.cleaned_data['username'].lower().strip()
        if not re.match(r'^[a-z0-9_]+$', username):
            raise forms.ValidationError('Solo letras minusculas, numeros y guiones bajos.')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Ese nombre de usuario ya esta en uso.')
        if len(username) < 4:
            raise forms.ValidationError('Minimo 4 caracteres.')
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError({'password2': 'Las contrasenas no coinciden.'})
        return cleaned


class WizardPaso3Form(forms.Form):
    telefono_taller = forms.CharField(
        label='Telefono del taller', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'})
    )
    direccion = forms.CharField(
        label='Direccion del taller', required=False, max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    mensaje_bienvenida = forms.CharField(
        label='Mensaje de bienvenida al cliente', required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text='Se incluye en el primer email que recibe el cliente.'
    )
    notif_email = forms.BooleanField(
        label='Activar notificaciones por email', required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class InvitarTecnicoForm(forms.Form):
    email = forms.EmailField(
        label='Email del tecnico',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tecnico@ejemplo.com'})
    )
    rol = forms.ChoiceField(
        label='Rol',
        choices=[('tecnico', 'Tecnico'), ('admin', 'Administrador')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
