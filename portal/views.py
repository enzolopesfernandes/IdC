import calendar
from datetime import date
from django.db.models import Sum
from django.shortcuts import render, redirect
from .forms import AttendanceForm
from .models import Attendance, Attachment, UNITS
from django.db import transaction

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
    unit = request.GET.get('unit', 'acailandia')
    if unit not in dict(UNITS):
        unit = 'acailandia'
    entries = Attendance.objects.filter(unit=unit, date__year=selected.year, date__month=selected.month)
    days = set(entries.values_list('date', flat=True))
    weeks = [[{'number': day.day, 'outside': day.month != selected.month, 'registered': day in days, 'today': day == date.today()} for day in week] for week in calendar.Calendar(firstweekday=6).monthdatescalendar(selected.year, selected.month)]
    previous = (selected.replace(day=1).toordinal() - 1)
    next_month = date(selected.year + (selected.month == 12), selected.month % 12 + 1, 1)
    return render(request, 'home.html', {'units': UNITS, 'unit': unit, 'unit_name': dict(UNITS)[unit], 'selected_month': selected.strftime('%Y-%m'), 'weeks': weeks, 'month_label': f'{MONTHS[selected.month - 1]}/{selected.year}', 'previous': date.fromordinal(previous).strftime('%Y-%m'), 'next': next_month.strftime('%Y-%m'), 'totals': entries.aggregate(expected=Sum('expected'), completed=Sum('completed'))})


def records(request):
    selected = period(request)
    entries = Attendance.objects.filter(date__year=selected.year, date__month=selected.month)
    rows = []
    for key, name in UNITS:
        records = entries.filter(unit=key)
        totals = records.aggregate(expected=Sum('expected'), completed=Sum('completed'))
        rows.append({'name': name, 'expected': totals['expected'] or 0, 'completed': totals['completed'] or 0, 'notes': list(records.exclude(notes='').values_list('notes', flat=True)), 'attachments': Attachment.objects.filter(attendance__in=records)})
    return render(request, 'records.html', {'rows': rows, 'selected_month': selected.strftime('%Y-%m'), 'month_label': f'{MONTHS[selected.month - 1]}/{selected.year}'})


def register(request):
    form = AttendanceForm(request.POST if request.method == 'POST' else None, request.FILES or None, initial={'date': date.today(), 'unit': request.GET.get('unit', 'acailandia')})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            attendance = form.save()
            for file in form.cleaned_data['media']:
                Attachment.objects.create(attendance=attendance, file=file, name=file.name[:255])
        return redirect(f'/?unit={attendance.unit}&month={attendance.date:%Y-%m}')
    return render(request, 'register.html', {'form': form})
