"""Resultados derivados do ORM; nenhuma gravação ou dependência externa."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum

from portal.models import Atendimento, Indicador, MetaMensal


def selecionar_metrica(indicador, totais, anual=False):
    if indicador.tipo_calculo is None:
        return None  # Indicador legado ainda não configurado.
    campos = {
        Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS: 'completed',
        Indicador.TipoCalculo.LIVROS_RETIRADOS: 'livros',
    }
    if indicador.tipo_calculo not in campos:
        raise ValidationError('Tipo de cálculo não suportado.')
    campo = campos[indicador.tipo_calculo] + ('_anual' if anual else '')
    return totais.get(campo, 0) or 0


def calcular_realizado(indicador, polo, competencia, *, anual=False):
    """Aceita uma date: o dia não altera o mês/ano selecionado."""
    if indicador.tipo_calculo is None:
        return None
    registros = Atendimento.objects.filter(polo=polo, data__year=competencia.year)
    if not anual:
        registros = registros.filter(data__month=competencia.month)
    if indicador.tipo_calculo == Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS:
        return registros.aggregate(valor=Count('pk'))['valor']
    if indicador.tipo_calculo == Indicador.TipoCalculo.LIVROS_RETIRADOS:
        return registros.aggregate(valor=Sum('livros_retirados'))['valor'] or 0
    raise ValidationError('Tipo de cálculo não suportado.')


def calcular_atingimento(realizado, previsto):
    """Percentual em pontos percentuais: 50 representa 50%, sem teto."""
    if realizado is None or previsto is None or previsto <= 0:
        return None
    return Decimal(realizado) / Decimal(previsto) * Decimal('100')


def resultados_por_polo(competencia, indicadores, polo_ids):
    """Duas consultas agrupadas para todos os polos/indicadores, sem N+1."""
    competencia = competencia.replace(day=1)
    polo_ids = list(polo_ids)
    indicadores = list(indicadores)
    totais = {
        item['polo_id']: item for item in Atendimento.objects.filter(
            polo_id__in=polo_ids, data__year=competencia.year,
        ).values('polo_id').annotate(
            completed=Count('pk', filter=Q(data__month=competencia.month)),
            livros=Sum('livros_retirados', filter=Q(data__month=competencia.month)),
            completed_anual=Count('pk'), livros_anual=Sum('livros_retirados'),
        ).order_by()
    }
    metas = {
        (item['polo_id'], item['indicador_id']): item for item in MetaMensal.objects.filter(
            polo_id__in=polo_ids, competencia__year=competencia.year,
        ).values('polo_id', 'indicador_id').annotate(
            mensal=Sum('previsto', filter=Q(competencia=competencia)), anual=Sum('previsto'),
        ).order_by()
    }
    resultados = {}
    for polo_id in polo_ids:
        resumo = totais.setdefault(polo_id, {})
        for campo in ['completed', 'livros', 'completed_anual', 'livros_anual']:
            resumo[campo] = resumo.get(campo) or 0
        resultados[polo_id] = []
        for indicador in indicadores:
            meta = metas.get((polo_id, indicador.pk), {'mensal': None, 'anual': None})
            realizado = selecionar_metrica(indicador, resumo)
            realizado_anual = selecionar_metrica(indicador, resumo, anual=True)
            resultados[polo_id].append({
                'indicador': indicador, **meta,
                'realizado': realizado, 'realizado_anual': realizado_anual,
                'atingimento': calcular_atingimento(realizado, meta['mensal']),
                'atingimento_anual': calcular_atingimento(realizado_anual, meta['anual']),
            })
    return resultados, totais
