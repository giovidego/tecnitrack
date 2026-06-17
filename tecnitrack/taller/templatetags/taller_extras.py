"""
TecniTrack - Filtros de template personalizados
Uso: {% load taller_extras %} en cualquier template
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Permite acceder a un dict por clave variable en templates.
    Uso: {{ mi_dict|get_item:variable }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, 0)
    return 0


@register.filter
def split(value, delimiter=','):
    """
    Divide un string por un delimitador.
    Uso: {{ "a,b,c"|split:"," }}
    """
    return value.split(delimiter)


@register.filter
def get_estado_clase(estado):
    """Devuelve la clase CSS Bootstrap según el estado de la orden."""
    clases = {
        'recibido': 'secondary',
        'diagnostico': 'info',
        'espera_repuestos': 'warning',
        'en_reparacion': 'primary',
        'listo': 'success',
        'entregado': 'dark',
        'cancelado': 'danger',
    }
    return clases.get(estado, 'secondary')
