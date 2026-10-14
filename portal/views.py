import calendar
from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import AtendimentoForm
from .services.indicadores import resultados_por_polo
from .models import AnexoAtendimento, Atendimento, Evento, Indicador, Polo

MONTHS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']


def period(request):
    today = date.today()
    try:
        selected = date.fromisoformat(request.GET.get('month', today.strftime('%Y-%m')) + '-01')
    except (ValueError, TypeError):
        selected = today.replace(day=1)
    return selected


def home(request):
    selected = period(request)
    polos = list(Polo.objects.all())
    try:
        polo_id = int(request.GET.get('unit', ''))
        polo = next((item for item in polos if item.pk == polo_id), None)
    except (TypeError, ValueError):
        polo = None
    polo = polo or (polos[0] if polos else None)
    entries = Atendimento.objects.filter(polo=polo, data__year=selected.year, data__month=selected.month)
    days = set(entries.values_list('data', flat=True))
    weeks = [[{'number': day.day, 'outside': day.month != selected.month, 'registered': day in days, 'today': day == date.today()} for day in week] for week in calendar.Calendar(firstweekday=6).monthdatescalendar(selected.year, selected.month)]
    previous = selected.toordinal() - 1
    next_month = date(selected.year + (selected.month == 12), selected.month % 12 + 1, 1)
    indicadores = list(Indicador.objects.order_by('nome', 'pk'))
    metas, totais = resultados_por_polo(selected, indicadores, [polo.pk] if polo else [])
    resumo = totais.get(polo.pk, {}) if polo else {}
    totals = {campo: resumo.get(campo, 0) for campo in ['completed', 'livros']}
    return render(request, 'home.html', {
        'units': [(str(item.pk), item.nome) for item in polos],
        'unit': str(polo.pk) if polo else '', 'polo': polo,
        'unit_name': polo.nome if polo else 'Nenhum polo cadastrado',
        'responsaveis': list(polo.responsaveis.order_by('nome', 'pk')) if polo else [],
        'eventos': list(Evento.objects.filter(polo=polo, data_inicio__lt=next_month, data_fim__gte=selected).order_by('data_inicio', 'pk')) if polo else [],
        'metas': metas.get(polo.pk, []) if polo else [],
        'selected_year': selected.year,
        'selected_month': selected.strftime('%Y-%m'), 'weeks': weeks,
        'month_label': f'{MONTHS[selected.month - 1]}/{selected.year}',
        'previous': date.fromordinal(previous).strftime('%Y-%m'), 'next': next_month.strftime('%Y-%m'),
        'totals': totals,
    })


def records(request):
    selected = period(request)
    entries = Atendimento.objects.filter(data__year=selected.year, data__month=selected.month)
    polos = list(Polo.objects.prefetch_related(Prefetch(
        'atendimentos', queryset=entries.prefetch_related('anexos'), to_attr='atendimentos_do_mes',
    )))
    indicadores = list(Indicador.objects.order_by('nome', 'pk'))
    metas, totais = resultados_por_polo(selected, indicadores, [polo.pk for polo in polos])
    rows = []
    for polo in polos:
        atendimentos = polo.atendimentos_do_mes
        rows.append({
            'name': polo.nome, 'ativo': polo.ativo,
            'livros': totais.get(polo.pk, {}).get('livros', 0) or 0,
            'completed': totais.get(polo.pk, {}).get('completed', 0),
            'notes': [item.observacao for item in atendimentos if item.observacao],
            'attachments': [anexo for item in atendimentos for anexo in item.anexos.all()],
            'metas': metas[polo.pk],
        })
    return render(request, 'records.html', {
        'rows': rows, 'selected_month': selected.strftime('%Y-%m'), 'selected_year': selected.year,
        'month_label': f'{MONTHS[selected.month - 1]}/{selected.year}',
    })


def register(request):
    form = AtendimentoForm(request.POST if request.method == 'POST' else None, request.FILES or None,
                           initial={'data': date.today(), 'polo': request.GET.get('unit')})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            atendimento = form.save()
            for file in form.cleaned_data['media']:
                AnexoAtendimento.objects.create(atendimento=atendimento, arquivo=file, nome_original=file.name[:255],
                                               tipo_mime=file.content_type or '', tamanho=file.size)
        messages.success(request, 'Atendimento registrado com sucesso.')
        destino = reverse('home') + '?' + urlencode({'unit': atendimento.polo_id, 'month': atendimento.data.strftime('%Y-%m')})
        return redirect(destino)
    return render(request, 'register.html', {'form': form})
