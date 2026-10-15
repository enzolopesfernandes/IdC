from django.contrib import admin
from .models import (Polo, ResponsavelPolo, Atendimento, Evento, Indicador,
                     MetaMensal, AnexoAtendimento, AnexoEvento)


@admin.register(Polo)
class PoloAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'parceiro', 'telefone']
    search_fields = ['nome', 'parceiro']
    list_filter = ['ativo']


@admin.register(ResponsavelPolo)
class ResponsavelPoloAdmin(admin.ModelAdmin):
    list_select_related = ['polo']
    list_display = ['nome', 'polo', 'email', 'ativo']
    search_fields = ['nome', 'email', 'polo__nome']
    list_filter = ['ativo', 'polo']


@admin.register(Atendimento)
class AtendimentoAdmin(admin.ModelAdmin):
    list_display = ['polo', 'data', 'livros_retirados', 'evento']
    search_fields = ['polo__nome', 'observacao']
    list_filter = ['polo', 'data']


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'polo', 'data_inicio', 'data_fim', 'status']
    search_fields = ['titulo', 'polo__nome']
    list_filter = ['polo', 'status']


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'tipo_calculo', 'ativo']
    search_fields = ['codigo', 'nome']
    list_filter = ['ativo', 'tipo_calculo']


@admin.register(MetaMensal)
class MetaMensalAdmin(admin.ModelAdmin):
    list_select_related = ['polo', 'indicador']
    list_display = ['polo', 'indicador', 'competencia', 'previsto']
    list_filter = ['polo', 'indicador', 'competencia']
    search_fields = ['polo__nome', 'indicador__codigo']


@admin.register(AnexoAtendimento)
class AnexoAtendimentoAdmin(admin.ModelAdmin):
    list_display = ['nome_original', 'atendimento', 'tipo_mime', 'tamanho', 'enviado_em']
    search_fields = ['nome_original']


@admin.register(AnexoEvento)
class AnexoEventoAdmin(admin.ModelAdmin):
    list_display = ['nome_original', 'evento', 'tipo_mime', 'tamanho', 'enviado_em']
    search_fields = ['nome_original']


from .models import PerfilUsuario


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ['user', 'tipo', 'polo']
    list_filter = ['tipo', 'polo']
    search_fields = ['user__username', 'polo__nome']

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_delete_permission = has_view_permission
