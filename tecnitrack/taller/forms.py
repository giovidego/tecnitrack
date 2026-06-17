"""
TecniTrack - Forms del taller (schema-based tenancy)
Sin referencias a Taller FK - los querysets no necesitan filtrar por taller.
"""
from django import forms
from django.contrib.auth.models import User
from .models import Cliente, Equipo, OrdenReparacion, Repuesto


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg', 'placeholder': 'tu_usuario', 'autofocus': True
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-lg', 'placeholder': '••••••••'
    }))


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'rut', 'email', 'telefono', 'direccion', 'notas']
        widgets = {
            'nombre':    forms.TextInput(attrs={'class': 'form-control'}),
            'apellido':  forms.TextInput(attrs={'class': 'form-control'}),
            'rut':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12.345.678-9'}),
            'email':     forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'notas':     forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ['tipo', 'marca', 'modelo', 'serial', 'descripcion', 'foto']
        widgets = {
            'tipo':        forms.Select(attrs={'class': 'form-select'}),
            'marca':       forms.TextInput(attrs={'class': 'form-control'}),
            'modelo':      forms.TextInput(attrs={'class': 'form-control'}),
            'serial':      forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'foto':        forms.FileInput(attrs={'class': 'form-control'}),
        }


class OrdenForm(forms.ModelForm):
    class Meta:
        model = OrdenReparacion
        fields = [
            'cliente', 'equipo', 'tecnico', 'problema_reportado',
            'accesorios_recibidos', 'prioridad', 'presupuesto',
            'fecha_estimada', 'notas_internas',
        ]
        widgets = {
            'cliente':             forms.Select(attrs={'class': 'form-select', 'id': 'id_cliente'}),
            'equipo':              forms.Select(attrs={'class': 'form-select', 'id': 'id_equipo'}),
            'tecnico':             forms.Select(attrs={'class': 'form-select'}),
            'problema_reportado':  forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'accesorios_recibidos': forms.TextInput(attrs={'class': 'form-control'}),
            'prioridad':           forms.Select(attrs={'class': 'form-select'}),
            'presupuesto':         forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_estimada':      forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notas_internas':      forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, cliente_inicial=None, equipo_inicial=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Sin filtro por taller — todos los objetos del schema pertenecen a este taller
        self.fields['cliente'].queryset = Cliente.objects.all()
        from .models import PerfilUsuario
        tecnicos_ids = PerfilUsuario.objects.filter(activo=True).values_list('usuario_id', flat=True)
        self.fields['tecnico'].queryset  = User.objects.filter(id__in=tecnicos_ids)
        self.fields['tecnico'].required  = False
        self.fields['tecnico'].empty_label = "Sin asignar"

        if cliente_inicial:
            self.fields['cliente'].initial = cliente_inicial
            self.fields['equipo'].queryset = Equipo.objects.filter(cliente=cliente_inicial)
        else:
            self.fields['equipo'].queryset = Equipo.objects.all()

        if equipo_inicial:
            self.fields['equipo'].initial = equipo_inicial


class CambioEstadoForm(forms.ModelForm):
    comentario = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label='Comentario para el cliente'
    )

    class Meta:
        model = OrdenReparacion
        fields = ['estado', 'diagnostico', 'solucion_aplicada',
                  'presupuesto', 'presupuesto_aprobado', 'costo_final', 'notas_internas']
        widgets = {
            'estado':               forms.Select(attrs={'class': 'form-select'}),
            'diagnostico':          forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'solucion_aplicada':    forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'presupuesto':          forms.NumberInput(attrs={'class': 'form-control'}),
            'presupuesto_aprobado': forms.Select(
                choices=[(None, '--- Pendiente ---'), (True, 'Aprobado'), (False, 'Rechazado')],
                attrs={'class': 'form-select'}
            ),
            'costo_final':    forms.NumberInput(attrs={'class': 'form-control'}),
            'notas_internas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class RepuestoForm(forms.ModelForm):
    class Meta:
        model = Repuesto
        fields = ['descripcion', 'cantidad', 'precio_unitario']
        widgets = {
            'descripcion':     forms.TextInput(attrs={'class': 'form-control'}),
            'cantidad':        forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control'}),
        }
