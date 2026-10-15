from django import forms
from .models import Atendimento, Polo


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MediaFilesField(forms.FileField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if len(files) > 2:
            raise forms.ValidationError('Envie no máximo 2 fotos por atendimento.')
        cleaned = []
        for item in files:
            file = super().clean(item, initial)
            if file.size > 2 * 1024 * 1024:
                raise forms.ValidationError('Cada foto deve ter no máximo 2 MB.')
            header = file.read(12)
            file.seek(0)
            extension = file.name.rsplit('.', 1)[-1].lower()
            valid = (extension in ('jpg', 'jpeg') and header.startswith(b'\xff\xd8\xff')) or (extension == 'png' and header.startswith(b'\x89PNG\r\n\x1a\n')) or (extension == 'webp' and header[:4] == b'RIFF' and header[8:12] == b'WEBP')
            if not valid:
                raise forms.ValidationError('Envie somente fotos JPG, PNG ou WebP válidas.')
            cleaned.append(file)
        return cleaned


class AtendimentoForm(forms.ModelForm):
    media = MediaFilesField(label='Fotos', required=False, widget=MultipleFileInput(attrs={'accept': '.jpg,.jpeg,.png,.webp'}), help_text='Até 2 fotos por atendimento, com no máximo 2 MB cada. Formatos JPG, PNG ou WebP.')
    class Meta:
        model = Atendimento
        fields = ['polo', 'data', 'livros_retirados', 'evento', 'observacao']
        labels = {'polo': 'Polo', 'data': 'Data do atendimento', 'livros_retirados': 'Livros retirados', 'evento': 'Evento (opcional)', 'observacao': 'Observações'}
        widgets = {'data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), 'observacao': forms.Textarea(attrs={'rows': 4})}
        error_messages = {
            'polo': {'required': 'Selecione um polo.', 'invalid_choice': 'Selecione um polo ativo válido.'},
            'data': {'required': 'Informe a data do atendimento.', 'invalid': 'Informe uma data válida.'},
            'livros_retirados': {
                'required': 'Informe a quantidade de livros retirados.',
                'invalid': 'Informe uma quantidade inteira válida.',
                'min_value': 'A quantidade de livros retirados não pode ser negativa.',
            },
            'evento': {'invalid_choice': 'Selecione um evento válido.'},
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['polo'].queryset = Polo.objects.filter(ativo=True)
        self.fields['evento'].queryset = self.fields['evento'].queryset.select_related('polo').order_by('titulo', 'pk')
        self.fields['evento'].label_from_instance = lambda evento: f'{evento.titulo} — {evento.polo.nome}'
        self.fields['evento'].help_text = 'Opcional. Se informado, deve pertencer ao polo selecionado.'
        if user is not None:
            from .access import administrador, escopo
            self.fields['evento'].queryset = escopo(user, self.fields['evento'].queryset)
            if not administrador(user):
                self.fields['polo'].queryset = escopo(user, Polo.objects.all(), 'pk')
                self.fields['polo'].initial = user.perfil.polo_id
                self.initial['polo'] = user.perfil.polo_id
                self.fields['polo'].disabled = True
                self.instance.polo_id = user.perfil.polo_id
        if self.instance.pk:
            self.fields.pop('media')
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
