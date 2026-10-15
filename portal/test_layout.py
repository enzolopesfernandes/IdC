from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Polo, PerfilUsuario, Indicador, MetaMensal, Atendimento


class MonthlyLayoutTests(TestCase):
    def setUp(self):
        self.a = Polo.objects.create(nome='Polo layout A')
        self.b = Polo.objects.create(nome='Polo layout B')
        self.admin = get_user_model().objects.create_user('layout-admin')
        PerfilUsuario.objects.create(user=self.admin, tipo='ADMIN')
        self.manager = get_user_model().objects.create_user('layout-manager')
        PerfilUsuario.objects.create(user=self.manager, tipo='GERENTE', polo=self.a)
        self.indicator = Indicador.objects.create(codigo='qtd', nome='Atendimentos', tipo_calculo='quantidade_atendimentos')
        self.books = Indicador.objects.create(codigo='books', nome='Livros', tipo_calculo='livros_retirados')
        MetaMensal.objects.create(polo=self.a, indicador=self.indicator, competencia=date(2026, 1, 1), previsto=2)
        MetaMensal.objects.create(polo=self.a, indicador=self.indicator, competencia=date(2026, 2, 1), previsto=0)
        for _ in range(3):
            Atendimento.objects.create(polo=self.a, data=date(2026, 1, 15), livros_retirados=4)
        self.client.force_login(self.admin)

    def test_home_cards_header_and_map(self):
        response = self.client.get('/', {'unit': self.a.pk, 'month': '2026-01'})
        self.assertContains(response, 'id="unit-form"')
        self.assertContains(response, 'class="indicator-card"', count=2)
        for text in ['ACOMPANHAMENTO MENSAL', 'Previsto mensal', 'Realizado mensal', 'Atingimento mensal', '150,00%', 'width:100%', 'Mapa será exibido aqui', 'Calendário de registros']:
            self.assertContains(response, text)
        for text in ['Previsto anual', 'Realizado anual', 'Atingimento anual', 'class="metrics"', '<iframe']:
            self.assertNotContains(response, text)
        header = response.content.decode().split('</header>')[0]
        self.assertNotIn(self.admin.username, header)
        self.assertNotIn('Admin', header)
        self.assertIn('/logout/', header)
        self.assertLess(response.content.decode().index('id="unit-form"'), response.content.decode().index('class="unit-grid"'))

    def test_manager_filter_and_scope_unchanged(self):
        self.client.force_login(self.manager)
        response = self.client.get('/', {'unit': self.b.pk})
        self.assertEqual(response.context['polo'], self.a)
        self.assertNotContains(response, 'id="unit-form"')
        self.assertNotContains(response, self.b.nome)
        response = self.client.get('/registros/', {'polo': self.b.pk, 'year': 2026})
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(response.context['rows'][0]['name'], self.a.nome)
        self.assertNotContains(response, 'id="polo"')

    def test_records_twelve_rows_per_indicator_order_values_and_no_annual(self):
        response = self.client.get('/registros/', {'polo': self.a.pk, 'year': 2026})
        sections = response.context['rows'][0]['sections']
        self.assertEqual(len(sections), 2)
        for section in sections:
            self.assertEqual([m['number'] for m in section['months']], list(range(1, 13)))
        months = sections[0]['months']
        self.assertEqual(months[0]['mensal'], Decimal(2))
        self.assertEqual(months[0]['realizado'], 3)
        self.assertEqual(months[0]['atingimento'], Decimal(150))
        self.assertEqual(months[1]['mensal'], Decimal(0))
        self.assertIsNone(months[1]['atingimento'])
        self.assertIsNone(months[2]['mensal'])
        self.assertEqual(months[2]['realizado'], 0)
        self.assertContains(response, '<tr data-month=', count=24)
        self.assertContains(response, '<th scope="col">', count=8)
        self.assertContains(response, 'role="progressbar"')
        self.assertContains(response, '150,00%')
        html = response.content.decode()
        self.assertLess(html.index('data-month="1"'), html.index('data-month="2"'))
        for text in ['Previsto anual', 'Realizado anual', 'Atingimento anual']:
            self.assertNotContains(response, text)

    def test_year_and_legacy_month_filter(self):
        for query in [{'year': 2025}, {'month': '2025-01'}]:
            response = self.client.get('/registros/', {'polo': self.a.pk, **query})
            self.assertEqual(response.context['selected_year'], 2025)
            months = response.context['rows'][0]['sections'][0]['months']
            self.assertTrue(all(m['mensal'] is None and m['realizado'] == 0 for m in months))
        for value in ['invalid', '0', '10000']:
            self.assertEqual(self.client.get('/registros/', {'year': value}).status_code, 200)
