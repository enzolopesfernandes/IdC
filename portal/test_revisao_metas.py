from datetime import date
from decimal import Decimal

from django.test import TestCase

from .models import Polo, Indicador, MetaMensal, Atendimento


class RevisaoMetasTelasTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser(username='test-access', password='test-pass'))
        self.polo = Polo.objects.create(nome='A\u00e7ail\u00e2ndia')
        self.outro = Polo.objects.create(nome='Polo com outra meta')
        self.sem_meta = Polo.objects.create(nome='Polo sem meta')
        self.indicador = Indicador.objects.create(codigo='atendimentos', nome='Atendimentos', tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS)
        MetaMensal.objects.create(polo=self.polo, indicador=self.indicador, competencia=date(2026, 4, 1), previsto=1800)
        MetaMensal.objects.create(polo=self.polo, indicador=self.indicador, competencia=date(2026, 5, 1), previsto=100)
        MetaMensal.objects.create(polo=self.polo, indicador=self.indicador, competencia=date(2025, 4, 1), previsto=700)
        MetaMensal.objects.create(polo=self.outro, indicador=self.indicador, competencia=date(2026, 4, 1), previsto=250)

    def home(self, polo=None, mes='2026-04'):
        return self.client.get('/', {'unit': (polo or self.polo).pk, 'month': mes})

    def test_acailandia_abril_meta_1800_na_home_e_registros(self):
        home = self.home()
        self.assertEqual(home.context['metas'][0]['mensal'], Decimal('1800'))
        self.assertContains(home, '<dd>1800</dd>', html=True)
        self.assertEqual(home.context['metas'][0]['realizado'], 0)
        self.assertEqual(home.context['metas'][0]['atingimento'], 0)
        registros = self.client.get('/registros/?month=2026-04')
        row = next(row for row in registros.context['rows'] if row['name'] == self.polo.nome)
        self.assertEqual(row['metas'][0]['mensal'], Decimal('1800'))

    def test_isolamento_por_polo_mes_ano_e_total_anual(self):
        self.assertEqual(self.home().context['metas'][0]['anual'], Decimal('1900'))
        self.assertEqual(self.home(self.outro).context['metas'][0]['mensal'], Decimal('250'))
        self.assertEqual(self.home(mes='2026-05').context['metas'][0]['mensal'], Decimal('100'))
        self.assertEqual(self.home(mes='2025-04').context['metas'][0]['mensal'], Decimal('700'))
        self.assertIsNone(self.home(mes='2027-04').context['metas'][0]['mensal'])

    def test_sem_meta_texto_explicito_sem_substituir_por_zero(self):
        response = self.home(self.sem_meta)
        self.assertContains(response, 'Sem meta cadastrada')
        meta = response.context['metas'][0]
        self.assertIsNone(meta['mensal'])
        self.assertIsNone(meta['anual'])
        self.assertIsNone(meta['atingimento'])
        self.assertEqual(meta['realizado'], 0)
        self.assertContains(self.client.get('/registros/?month=2026-04'), 'Sem meta cadastrada')

    def test_zero_explicito_distinto_de_meta_ausente(self):
        MetaMensal.objects.create(polo=self.sem_meta, indicador=self.indicador, competencia=date(2026, 4, 1), previsto=0)
        response = self.home(self.sem_meta)
        self.assertNotContains(response, 'Sem meta cadastrada')
        self.assertContains(response, '<dd>0</dd>', html=True)
        self.assertEqual(response.context['metas'][0]['mensal'], Decimal('0'))
        self.assertIsNone(response.context['metas'][0]['atingimento'])

    def test_mes_ausente_preserva_previsao_anual_existente(self):
        response = self.home(mes='2026-06')
        self.assertContains(response, 'Sem meta cadastrada')
        self.assertNotContains(response, '1900,00')
        self.assertIsNone(response.context['metas'][0]['mensal'])
        self.assertEqual(response.context['metas'][0]['anual'], Decimal('1900'))

    def test_percentual_da_linha_usa_seu_polo_e_indicador(self):
        livros = Indicador.objects.create(codigo='livros', nome='Livros', tipo_calculo=Indicador.TipoCalculo.LIVROS_RETIRADOS)
        MetaMensal.objects.create(polo=self.polo, indicador=livros, competencia=date(2026, 4, 1), previsto=10)
        Atendimento.objects.create(polo=self.polo, data=date(2026, 4, 1), livros_retirados=15)
        Atendimento.objects.create(polo=self.outro, data=date(2026, 4, 1), livros_retirados=999)
        Atendimento.objects.create(polo=self.polo, data=date(2026, 5, 1), livros_retirados=999)
        response = self.home()
        metas = {meta['indicador'].pk: meta for meta in response.context['metas']}
        self.assertEqual(metas[self.indicador.pk]['realizado'], 1)
        self.assertEqual(metas[livros.pk]['realizado'], 15)
        self.assertEqual(metas[livros.pk]['atingimento'], Decimal('150'))
        self.assertContains(response, '150,00%')
        registros = self.client.get('/registros/?month=2026-04')
        row = next(row for row in registros.context['rows'] if row['name'] == self.polo.nome)
        self.assertEqual({meta['indicador'].pk: meta for meta in row['metas']}[livros.pk]['atingimento'], Decimal('150'))

    def test_consultas_das_telas_nao_modificam_cadastros(self):
        from .models import ResponsavelPolo, Evento, AnexoAtendimento, AnexoEvento
        models = [Polo, Indicador, MetaMensal, Atendimento, ResponsavelPolo, Evento, AnexoAtendimento, AnexoEvento]
        antes = {model.__name__: list(model.objects.order_by('pk').values()) for model in models}
        self.home()
        self.home(self.sem_meta)
        self.client.get('/registros/?month=2026-04')
        depois = {model.__name__: list(model.objects.order_by('pk').values()) for model in models}
        self.assertEqual(antes, depois)
