from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, Q


class RegistroTemporal(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Polo(RegistroTemporal):
    legacy_sharepoint_id = models.PositiveBigIntegerField(null=True, blank=True)
    nome = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)
    parceiro = models.CharField(max_length=200, blank=True)
    horario_funcionamento = models.CharField(max_length=200, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    foto = models.FileField(upload_to='polos/%Y/%m/', blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])

    class Meta:
        ordering = ['nome', 'pk']

    def __str__(self):
        return self.nome


class ResponsavelPolo(RegistroTemporal):
    polo = models.ForeignKey(Polo, on_delete=models.PROTECT, related_name='responsaveis')
    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class Evento(RegistroTemporal):
    legacy_sharepoint_id = models.PositiveBigIntegerField(null=True, blank=True)
    titulo = models.CharField(max_length=200)
    polo = models.ForeignKey(Polo, on_delete=models.PROTECT, related_name='eventos')
    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(data_fim__gte=F('data_inicio')), name='evento_datas_validas')]

    def clean(self):
        super().clean()
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({'data_fim': 'A data final deve ser igual ou posterior à inicial.'})

    def __str__(self):
        return self.titulo


class Atendimento(RegistroTemporal):
    legacy_sharepoint_id = models.PositiveBigIntegerField(null=True, blank=True)
    polo = models.ForeignKey(Polo, on_delete=models.PROTECT, related_name='atendimentos')
    data = models.DateField()
    livros_retirados = models.PositiveIntegerField(default=0)
    observacao = models.TextField(blank=True, max_length=2000)
    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name='atendimentos', null=True, blank=True)

    class Meta:
        ordering = ['-data', 'polo']
        constraints = [models.CheckConstraint(condition=Q(livros_retirados__gte=0), name='atendimento_livros_nao_negativos')]

    def clean(self):
        super().clean()
        if self.evento_id and self.polo_id and self.evento.polo_id != self.polo_id:
            raise ValidationError({'evento': 'O evento deve pertencer ao polo do atendimento.'})

    def __str__(self):
        return f'{self.polo} — {self.data}'


class Indicador(RegistroTemporal):
    class TipoCalculo(models.TextChoices):
        QUANTIDADE_ATENDIMENTOS = 'quantidade_atendimentos', 'Quantidade de atendimentos'
        LIVROS_RETIRADOS = 'livros_retirados', 'Livros retirados'

    codigo = models.CharField(max_length=80, unique=True)
    nome = models.CharField(max_length=200)
    tipo_calculo = models.CharField(max_length=30, choices=TipoCalculo.choices, null=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(tipo_calculo__isnull=True) | Q(tipo_calculo__in=['quantidade_atendimentos', 'livros_retirados']),
            name='indicador_tipo_calculo_valido',
        )]

    def save(self, *args, **kwargs):
        if self._state.adding and self.tipo_calculo not in self.TipoCalculo.values:
            raise ValidationError({'tipo_calculo': 'Selecione o tipo de cálculo para o novo indicador.'})
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class MetaMensal(RegistroTemporal):
    polo = models.ForeignKey(Polo, on_delete=models.PROTECT, related_name='metas_mensais')
    indicador = models.ForeignKey(Indicador, on_delete=models.PROTECT, related_name='metas_mensais')
    competencia = models.DateField(help_text='Use o primeiro dia do mês, por exemplo 2026-01-01.')
    previsto = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['polo', 'indicador', 'competencia'], name='meta_polo_indicador_mes_unico'),
            models.CheckConstraint(condition=Q(previsto__gte=0), name='meta_previsto_nao_negativo'),
            models.CheckConstraint(condition=Q(competencia__day=1), name='meta_competencia_primeiro_dia'),
        ]

    def clean(self):
        super().clean()
        if self.competencia and self.competencia.day != 1:
            raise ValidationError({'competencia': 'Informe o primeiro dia do mês.'})

    def __str__(self):
        return f'{self.polo} / {self.indicador} / {self.competencia:%Y-%m}'


class AnexoBase(models.Model):
    nome_original = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=127, blank=True)
    tamanho = models.PositiveBigIntegerField(default=0)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.nome_original


class AnexoAtendimento(AnexoBase):
    atendimento = models.ForeignKey(Atendimento, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='atendimentos/%Y/%m/')


class AnexoEvento(AnexoBase):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='eventos/%Y/%m/')
