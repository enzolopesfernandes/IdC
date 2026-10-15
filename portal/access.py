from django.core.exceptions import PermissionDenied
from .models import PerfilUsuario


def perfil_acesso(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied
    if user.is_superuser:
        return None
    try:
        perfil = user.perfil
    except PerfilUsuario.DoesNotExist:
        raise PermissionDenied('Solicite ao administrador a configuração do seu perfil.')
    if (perfil.tipo == 'ADMIN' and perfil.polo_id is None) or (perfil.tipo == 'GERENTE' and perfil.polo_id):
        return perfil
    raise PermissionDenied('Perfil inválido.')


def administrador(user):
    perfil = perfil_acesso(user)
    return perfil is None or perfil.tipo == 'ADMIN'


def escopo(user, queryset, campo='polo_id'):
    perfil = perfil_acesso(user)
    if perfil is None or perfil.tipo == 'ADMIN':
        return queryset
    return queryset.filter(**{campo: perfil.polo_id})
