import calendar
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.views.decorators.http import require_http_methods
from .access import administrador, escopo
from .models import AnexoEvento

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


@login_required
def home(request):
    selected = period(request)
    polos = list(escopo(request.user, Polo.objects.all(), 'pk'))
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
        'is_admin': administrador(request.user),
        'units': [(str(item.pk), item.nome) for item in polos],
        'unit': str(polo.pk) if polo else '', 'polo': polo,
        'unit_name': polo.nome if polo else 'Nenhum polo cadastrado',
        'responsaveis': list(polo.responsaveis.order_by('nome', 'pk')) if polo else [],
        'eventos': list(Evento.objects.filter(polo=polo, data_inicio__lt=next_month, data_fim__gte=selected).order_by('data_inicio', 'pk')) if polo else [],
        'metas': metas.get(polo.pk, []) if polo else [],
        'show_completed': not any(i.tipo_calculo == 'quantidade_atendimentos' for i in indicadores),
        'show_books': not any(i.tipo_calculo == 'livros_retirados' for i in indicadores),
        'selected_year': selected.year,
        'selected_month': selected.strftime('%Y-%m'), 'weeks': weeks,
        'month_label': f'{MONTHS[selected.month - 1]}/{selected.year}',
        'previous': date.fromordinal(previous).strftime('%Y-%m'), 'next': next_month.strftime('%Y-%m'),
        'totals': totals,
    })


@login_required
def records(request):
    selected = period(request)
    try:
        selected = selected.replace(year=int(request.GET.get('year', selected.year)))
    except (ValueError, TypeError):
        pass
    entries = Atendimento.objects.filter(data__year=selected.year, data__month=selected.month)
    polos_query = escopo(request.user, Polo.objects.all(), 'pk')
    if administrador(request.user) and request.GET.get('polo'):
        polos_query = polos_query.filter(pk=request.GET['polo']) if request.GET['polo'].isdigit() else polos_query.none()
    polos = list(polos_query.prefetch_related(Prefetch(
        'atendimentos', queryset=entries.prefetch_related('anexos'), to_attr='atendimentos_do_mes',
    )))
    indicadores = list(Indicador.objects.order_by('nome', 'pk'))
    metas, totais = resultados_por_polo(selected, indicadores, [polo.pk for polo in polos])
    # Reuse the service per month, batching all authorized polos together.
    monthly = {selected.month: metas}
    for month in range(1, 13):
        if month != selected.month:
            monthly[month], _ = resultados_por_polo(date(selected.year, month, 1), indicadores, [p.pk for p in polos])
    rows = []
    for polo in polos:
        atendimentos = polo.atendimentos_do_mes
        rows.append({
            'name': polo.nome, 'ativo': polo.ativo, 'entries': atendimentos,
            'livros': totais.get(polo.pk, {}).get('livros', 0) or 0,
            'completed': totais.get(polo.pk, {}).get('completed', 0),
            'notes': [item.observacao for item in atendimentos if item.observacao],
            'attachments': [anexo for item in atendimentos for anexo in item.anexos.all()],
            'metas': metas[polo.pk],
            'sections': [
                {'indicador': indicador, 'months': [
                    {'name': MONTHS[month - 1], 'number': month, **monthly[month][polo.pk][index]}
                    for month in range(1, 13)
                ]} for index, indicador in enumerate(indicadores)
            ],
        })
    return render(request, 'records.html', {
        'is_admin': administrador(request.user), 'polos': escopo(request.user, Polo.objects.all(), 'pk'),
        'rows': rows, 'selected_month': selected.strftime('%Y-%m'), 'selected_year': selected.year,
        'month_label': f'{MONTHS[selected.month - 1]}/{selected.year}',
    })


@login_required
def register(request):
    administrador(request.user)
    form = AtendimentoForm(request.POST if request.method == 'POST' else None, request.FILES or None,
                           initial={'data': date.today(), 'polo': request.GET.get('unit')}, user=request.user)
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


@login_required
@require_http_methods(['GET', 'POST'])
def edit_atendimento(request, pk):
    atendimento = get_object_or_404(escopo(request.user, Atendimento.objects.all()), pk=pk)
    form = AtendimentoForm(request.POST if request.method == 'POST' else None,
                           instance=atendimento, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Atendimento atualizado com sucesso.')
        return redirect('records')
    return render(request, 'register.html', {'form': form, 'editing': True})


@login_required
@require_http_methods(['GET', 'POST'])
def delete_atendimento(request, pk):
    if not administrador(request.user):
        raise PermissionDenied
    atendimento = get_object_or_404(Atendimento, pk=pk)
    if request.method == 'POST':
        atendimento.delete()
        messages.success(request, 'Atendimento excluido com sucesso.')
        return redirect('records')
    return render(request, 'delete_atendimento.html', {'atendimento': atendimento})


@login_required
def protected_media(request, path):
    # Resolve known database references, never an arbitrary filesystem path.
    for model, relation in [(AnexoAtendimento, 'atendimento__polo_id'), (AnexoEvento, 'evento__polo_id')]:
        anexo = escopo(request.user, model.objects.filter(arquivo=path), relation).first()
        if anexo:
            try:
                return FileResponse(anexo.arquivo.open('rb'), as_attachment=True, filename=anexo.nome_original)
            except FileNotFoundError:
                raise Http404
    polo = escopo(request.user, Polo.objects.filter(foto=path), 'pk').first()
    if polo:
        try:
            return FileResponse(polo.foto.open('rb'))
        except FileNotFoundError:
            raise Http404
    raise Http404
