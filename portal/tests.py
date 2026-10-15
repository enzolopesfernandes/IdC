from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings

from .models import (Polo, ResponsavelPolo, Atendimento, Evento, Indicador,
                     MetaMensal, AnexoAtendimento, AnexoEvento)


class ModelagemTests(TestCase):
    def setUp(self):
        self.polo = Polo.objects.create(nome='Polo de teste')
        self.indicador = Indicador.objects.create(tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS, codigo='teste', nome='Indicador de teste')

    def evento(self, **kwargs):
        values = {'polo': self.polo, 'titulo': 'Evento de teste',
                  'data_inicio': date(2026, 1, 10), 'data_fim': date(2026, 1, 11)}
        values.update(kwargs)
        return Evento(**values)

    def meta(self, **kwargs):
        values = {'polo': self.polo, 'indicador': self.indicador,
                  'competencia': date(2026, 1, 1), 'previsto': Decimal('100.50')}
        values.update(kwargs)
        return MetaMensal(**values)

    def test_criacao_polo_e_campos_opcionais(self):
        self.polo.full_clean()
        self.assertIsNotNone(self.polo.pk)
        self.assertTrue(self.polo.ativo)
        self.assertIsNone(self.polo.legacy_sharepoint_id)
        self.assertIsNotNone(self.polo.criado_em)
        with self.assertRaises(ValidationError):
            Polo(nome='').full_clean()
        with self.assertRaises(ValidationError):
            Polo(nome='Teste', latitude=91).full_clean()

    def test_polo_possui_varios_responsaveis(self):
        for nome in ['Responsavel A', 'Responsavel B']:
            ResponsavelPolo.objects.create(polo=self.polo, nome=nome)
        self.assertEqual(self.polo.responsaveis.count(), 2)
        with self.assertRaises(ProtectedError):
            self.polo.delete()

    def test_atendimento_polo_e_evento_opcional(self):
        atendimento = Atendimento.objects.create(polo=self.polo, data=date(2026, 1, 10), livros_retirados=3)
        atendimento.full_clean()
        self.assertEqual(self.polo.atendimentos.get(), atendimento)
        self.assertIsNone(atendimento.evento)
        with self.assertRaises(ProtectedError):
            self.polo.delete()

    def test_polo_obrigatorio_no_banco(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Atendimento.objects.create(data=date(2026, 1, 10))

    def test_evento_polo_e_atendimento(self):
        evento = self.evento()
        evento.save()
        atendimento = Atendimento.objects.create(polo=self.polo, evento=evento, data=date(2026, 1, 10))
        atendimento.full_clean()
        self.assertEqual(self.polo.eventos.get(), evento)
        self.assertEqual(evento.atendimentos.get(), atendimento)
        with self.assertRaises(ProtectedError):
            evento.delete()

    def test_evento_de_outro_polo_rejeitado_na_validacao(self):
        outro = Polo.objects.create(nome='Outro polo de teste')
        evento = self.evento(polo=outro)
        evento.save()
        with self.assertRaises(ValidationError):
            Atendimento(polo=self.polo, evento=evento, data=date(2026, 1, 10)).full_clean()

    def test_livros_negativos_rejeitados(self):
        atendimento = Atendimento(polo=self.polo, data=date(2026, 1, 10), livros_retirados=-1)
        with self.assertRaises(ValidationError):
            atendimento.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            atendimento.save()

    def test_datas_evento_invalidas_rejeitadas(self):
        evento = self.evento(data_fim=date(2026, 1, 9))
        with self.assertRaises(ValidationError):
            evento.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            evento.save()

    def test_evento_mesmo_dia_e_status_livre(self):
        evento = self.evento(data_fim=date(2026, 1, 10), status='Status a definir')
        evento.full_clean()
        evento.save()

    def test_meta_unica_por_polo_indicador_mes(self):
        self.meta().save()
        with self.assertRaises(ValidationError):
            self.meta().full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.meta().save()
        self.meta(competencia=date(2026, 2, 1)).save()
        self.assertEqual(MetaMensal.objects.count(), 2)
        with self.assertRaises(ProtectedError):
            self.indicador.delete()

    def test_previsto_negativo_rejeitado(self):
        meta = self.meta(previsto=Decimal('-0.01'))
        with self.assertRaises(ValidationError):
            meta.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            meta.save()

    def test_competencia_primeiro_dia(self):
        meta = self.meta(competencia=date(2026, 1, 15))
        with self.assertRaises(ValidationError):
            meta.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            meta.save()

    def test_codigo_indicador_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Indicador.objects.create(tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS, codigo='teste', nome='Outro')

    def test_anexos_evento_referencia_e_cascata(self):
        evento = self.evento()
        evento.save()
        with TemporaryDirectory(dir='.') as directory, override_settings(MEDIA_ROOT=directory):
            anexo = AnexoEvento.objects.create(evento=evento, arquivo=SimpleUploadedFile('teste.pdf', b'%PDF-1.4'),
                                               nome_original='teste.pdf', tipo_mime='application/pdf', tamanho=8)
            self.assertTrue(anexo.arquivo.storage.exists(anexo.arquivo.name))
            self.assertTrue(anexo.arquivo.name.startswith('eventos/'))
            self.assertIsNotNone(anexo.enviado_em)
            evento.delete()
            self.assertFalse(AnexoEvento.objects.exists())

    def test_models_registrados_no_admin(self):
        for model in [Polo, ResponsavelPolo, Atendimento, Evento, Indicador, MetaMensal, AnexoAtendimento, AnexoEvento]:
            self.assertTrue(admin.site.is_registered(model))


class PortalTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser(username='test-access', password='test-pass'))
        self.polo = Polo.objects.create(nome='Imperatriz')

    def dados(self):
        return {'polo': self.polo.pk, 'data': '2026-08-18', 'livros_retirados': 4}

    def test_paginas_e_admin_disponiveis(self):
        for path in ['/', '/registros/', '/atendimentos/novo/']:
            self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.get(f'/?unit={self.polo.pk}')
        self.assertContains(response, 'Unidade de Imperatriz')
        self.assertContains(response, 'img/sesi.svg')
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_paginas_sem_cadastros(self):
        self.polo.delete()
        for path in ['/', '/registros/', '/atendimentos/novo/']:
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertContains(self.client.get('/'), 'Nenhum polo cadastrado')
        self.assertEqual(Polo.objects.count(), 0)

    def test_multiple_attachments_and_links(self):
        with TemporaryDirectory(dir='.') as directory, override_settings(MEDIA_ROOT=directory):
            data = self.dados()
            data['media'] = [SimpleUploadedFile('foto.jpg', b'\xff\xd8\xffexample', content_type='image/jpeg'),
                             SimpleUploadedFile('foto.png', b'\x89PNG\r\n\x1a\nexample', content_type='image/png')]
            response = self.client.post('/atendimentos/novo/', data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Atendimento.objects.count(), 1)
            self.assertEqual(AnexoAtendimento.objects.count(), 2)
            for item in AnexoAtendimento.objects.all():
                self.assertTrue(item.arquivo.storage.exists(item.arquivo.name))
                self.assertGreater(item.tamanho, 0)
                self.assertTrue(item.tipo_mime)
            response = self.client.get('/registros/?month=2026-08')
            self.assertContains(response, 'foto.jpg')
            self.assertContains(response, 'foto.png')

    def test_invalid_attachment_prevents_save(self):
        data = self.dados()
        data['media'] = SimpleUploadedFile('fake.pdf', b'invalid')
        self.assertEqual(self.client.post('/atendimentos/novo/', data).status_code, 200)
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_rejeita_tres_fotos_sem_salvar_atendimento(self):
        data = self.dados()
        data['media'] = [SimpleUploadedFile(f'foto{i}.png', b'\x89PNG\r\n\x1a\nexample') for i in range(3)]
        response = self.client.post('/atendimentos/novo/', data)
        self.assertContains(response, 'Envie no máximo 2 fotos por atendimento.')
        self.assertFalse(Atendimento.objects.exists())
        self.assertFalse(AnexoAtendimento.objects.exists())

    def test_rejeita_foto_acima_de_dois_mb(self):
        data = self.dados()
        data['media'] = SimpleUploadedFile('foto.png', b'\x89PNG\r\n\x1a\n' + b'x' * (2 * 1024 * 1024 - 7))
        response = self.client.post('/atendimentos/novo/', data)
        self.assertContains(response, 'Cada foto deve ter no máximo 2 MB.')
        self.assertFalse(Atendimento.objects.exists())

    def test_aceita_foto_com_exatamente_dois_mb(self):
        with TemporaryDirectory(dir='.') as directory, override_settings(MEDIA_ROOT=directory):
            data = self.dados()
            data['media'] = SimpleUploadedFile('foto.webp', b'RIFFxxxxWEBP' + b'x' * (2 * 1024 * 1024 - 12), content_type='image/webp')
            self.assertEqual(self.client.post('/atendimentos/novo/', data).status_code, 302)
            self.assertEqual(AnexoAtendimento.objects.get().tamanho, 2 * 1024 * 1024)

    def test_rejeita_pdf_mesmo_com_assinatura_valida(self):
        data = self.dados()
        data['media'] = SimpleUploadedFile('documento.pdf', b'%PDF-1.4 example', content_type='application/pdf')
        response = self.client.post('/atendimentos/novo/', data)
        self.assertContains(response, 'Envie somente fotos JPG, PNG ou WebP válidas.')
        self.assertFalse(Atendimento.objects.exists())

    def test_formulario_rejeita_evento_de_outro_polo(self):
        outro = Polo.objects.create(nome='Outro polo')
        evento = Evento.objects.create(polo=outro, titulo='Teste', data_inicio=date(2026, 8, 18), data_fim=date(2026, 8, 18))
        data = self.dados()
        data['evento'] = evento.pk
        self.assertEqual(self.client.post('/atendimentos/novo/', data).status_code, 200)
        self.assertEqual(Atendimento.objects.count(), 0)

class IntegracaoCadastrosTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser(username='test-access', password='test-pass'))
        self.polo = Polo.objects.create(nome='Polo Integracao', parceiro='Parceiro cadastrado',
                                        horario_funcionamento='08h a 17h', foto='polos/foto-teste.jpg')
        self.outro = Polo.objects.create(nome='Outro polo', ativo=False)
        self.indicador = Indicador.objects.create(tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS, codigo='meta-a', nome='Indicador A')
        self.outro_indicador = Indicador.objects.create(tipo_calculo=Indicador.TipoCalculo.LIVROS_RETIRADOS, codigo='meta-b', nome='Indicador B', ativo=False)
        MetaMensal.objects.create(polo=self.polo, indicador=self.indicador, competencia=date(2026, 1, 1), previsto='100.25')
        MetaMensal.objects.create(polo=self.polo, indicador=self.indicador, competencia=date(2026, 2, 1), previsto='200.50')
        MetaMensal.objects.create(polo=self.polo, indicador=self.indicador, competencia=date(2025, 1, 1), previsto='999')
        MetaMensal.objects.create(polo=self.outro, indicador=self.indicador, competencia=date(2026, 1, 1), previsto='700')
        MetaMensal.objects.create(polo=self.polo, indicador=self.outro_indicador, competencia=date(2026, 1, 1), previsto='5')

    def home(self, **kwargs):
        return self.client.get('/', {'unit': self.polo.pk, 'month': '2026-01', **kwargs})

    def test_dados_reais_polo_foto_e_multiplos_responsaveis(self):
        ResponsavelPolo.objects.create(polo=self.polo, nome='Pessoa A')
        ResponsavelPolo.objects.create(polo=self.polo, nome='Pessoa B', ativo=False)
        ResponsavelPolo.objects.create(polo=self.outro, nome='Pessoa de outro polo')
        response = self.home()
        for value in ['Polo Integracao', 'Parceiro cadastrado', '08h a 17h', 'Pessoa A', 'Pessoa B', '/media/polos/foto-teste.jpg']:
            self.assertContains(response, value)
        self.assertNotContains(response, 'Pessoa de outro polo')
        self.assertNotContains(response, 'Imagem de exemplo')

    def test_polo_inativo_visivel_e_selecionavel(self):
        response = self.home(unit=self.outro.pk)
        self.assertEqual(response.context['polo'], self.outro)
        self.assertContains(response, 'Inativo')
        self.assertContains(response, 'Outro polo')
        self.assertContains(self.client.get('/registros/?month=2026-01'), '(inativo)')

    def test_metas_mensais_anuais_isoladas_por_polo_indicador_e_ano(self):
        response = self.home()
        metas = {item['indicador'].pk: item for item in response.context['metas']}
        self.assertEqual(metas[self.indicador.pk]['mensal'], Decimal('100.25'))
        self.assertEqual(metas[self.indicador.pk]['anual'], Decimal('300.75'))
        self.assertEqual(metas[self.outro_indicador.pk]['anual'], Decimal('5'))
        self.assertContains(response, 'Indicador A')
        self.assertContains(response, 'Indicador B')
        self.assertNotContains(response, 'Previsto anual')
        self.assertContains(response, '<dd>100</dd>', html=True)
        self.assertNotContains(response, '300,75')

    def test_filtro_mes_e_ano_altera_metas(self):
        response = self.home(month='2026-02')
        metas = {item['indicador'].pk: item for item in response.context['metas']}
        self.assertEqual(metas[self.indicador.pk]['mensal'], Decimal('200.50'))
        self.assertIsNone(metas[self.outro_indicador.pk]['mensal'])
        response = self.home(month='2025-01')
        self.assertEqual(response.context['metas'][0]['anual'], Decimal('999'))
        self.assertContains(response, '?month=2025-01')

    def test_meta_zero_diferente_de_meta_ausente(self):
        MetaMensal.objects.create(polo=self.polo, indicador=self.indicador, competencia=date(2027, 1, 1), previsto=0)
        response = self.home(month='2027-01')
        metas = {item['indicador'].pk: item for item in response.context['metas']}
        self.assertEqual(metas[self.indicador.pk]['mensal'], Decimal('0'))
        self.assertIsNone(metas[self.outro_indicador.pk]['mensal'])
        self.assertContains(response, '<dd>0</dd>', html=True)

    def test_realizados_sem_registros_sao_zero(self):
        response = self.home()
        self.assertEqual(response.context['totals'], {'completed': 0, 'livros': 0})

    def test_consulta_consolidada_preserva_metas_e_totais(self):
        Atendimento.objects.create(polo=self.polo, data=date(2026, 1, 10), livros_retirados=4)
        Atendimento.objects.create(polo=self.polo, data=date(2026, 1, 11), livros_retirados=2)
        Atendimento.objects.create(polo=self.polo, data=date(2026, 2, 1), livros_retirados=50)
        response = self.client.get('/registros/?month=2026-01')
        row = next(item for item in response.context['rows'] if item['name'] == self.polo.nome)
        self.assertEqual(row['completed'], 2)
        self.assertEqual(row['livros'], 6)
        self.assertEqual(row['metas'][0]['anual'], Decimal('300.75'))
        self.assertContains(response, 'Previsto')

    def test_consultas_nao_crescem_com_numero_de_polos(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        Atendimento.objects.create(polo=self.polo, data=date(2026, 1, 10))
        with CaptureQueriesContext(connection) as before:
            self.client.get('/registros/?month=2026-01')
        for index in range(5):
            polo = Polo.objects.create(nome=f'Polo extra {index}')
            atendimento = Atendimento.objects.create(polo=polo, data=date(2026, 1, 10))
            AnexoAtendimento.objects.create(atendimento=atendimento, arquivo='atendimentos/teste.pdf', nome_original='teste.pdf')
            MetaMensal.objects.create(polo=polo, indicador=self.indicador, competencia=date(2026, 1, 1), previsto=5)
        with CaptureQueriesContext(connection) as after:
            response = self.client.get('/registros/?month=2026-01')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(before), len(after))
        self.assertLessEqual(len(after), 31)  # Twelve months, still independent of polo count.

    def test_interface_sem_indicadores_e_sem_metas(self):
        MetaMensal.objects.all().delete()
        Indicador.objects.all().delete()
        self.assertContains(self.home(), 'Nenhum indicador cadastrado')
        self.assertEqual(self.client.get('/registros/').status_code, 200)
        self.assertEqual(Indicador.objects.count(), 0)

    def test_parametros_invalidos_usam_estado_valido(self):
        self.assertEqual(self.home(unit='invalido', month='invalido').status_code, 200)
        self.assertEqual(self.home(unit=99999999999999999999999999999).status_code, 200)

    def test_paginas_nao_dependem_de_rede_ou_sharepoint(self):
        from unittest.mock import patch
        with patch('socket.create_connection', side_effect=AssertionError('Sem rede')), patch('urllib.request.urlopen', side_effect=AssertionError('Sem rede')):
            self.assertEqual(self.home().status_code, 200)
            self.assertEqual(self.client.get('/registros/?month=2026-01').status_code, 200)

    def test_admin_rejeita_meta_duplicada_ou_negativa(self):
        from django.contrib.auth import get_user_model
        usuario = get_user_model().objects.create_superuser(username='admin-teste', password='senha-apenas-no-teste')
        self.client.force_login(usuario)
        url = '/admin/portal/metamensal/add/'
        dados = {'polo': self.polo.pk, 'indicador': self.indicador.pk, 'competencia': '2026-01-01', 'previsto': '10', '_save': 'Salvar'}
        before = MetaMensal.objects.count()
        response = self.client.post(url, dados)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['adminform'].form.errors)
        dados.update(competencia='2026-03-01', previsto='-1')
        response = self.client.post(url, dados)
        self.assertIn('previsto', response.context['adminform'].form.errors)
        self.assertEqual(MetaMensal.objects.count(), before)

class CalculoIndicadoresTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser(username='test-access', password='test-pass'))
        from .services.indicadores import calcular_realizado, calcular_atingimento, resultados_por_polo
        self.calcular = calcular_realizado
        self.percentual = calcular_atingimento
        self.resultados = resultados_por_polo
        self.polo = Polo.objects.create(nome='Polo de calculo')
        self.outro = Polo.objects.create(nome='Outro polo de calculo')
        self.quantidade = Indicador.objects.create(codigo='qtd', nome='Nome livre Q', tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS)
        self.livros = Indicador.objects.create(codigo='liv', nome='Nome livre L', tipo_calculo=Indicador.TipoCalculo.LIVROS_RETIRADOS)
        self.competencia = date(2026, 10, 1)
        for quantidade, dia in [(5, 1), (8, 15), (2, 31)]:
            Atendimento.objects.create(polo=self.polo, data=date(2026, 10, dia), livros_retirados=quantidade)
        Atendimento.objects.create(polo=self.outro, data=date(2026, 10, 1), livros_retirados=999)
        Atendimento.objects.create(polo=self.polo, data=date(2026, 9, 30), livros_retirados=20)
        Atendimento.objects.create(polo=self.polo, data=date(2026, 11, 1), livros_retirados=30)
        Atendimento.objects.create(polo=self.polo, data=date(2025, 10, 1), livros_retirados=888)

    def test_count_mensal(self):
        self.assertEqual(self.calcular(self.quantidade, self.polo, self.competencia), 3)

    def test_sum_mensal_e_isolamento_de_polo_mes_ano(self):
        self.assertEqual(self.calcular(self.livros, self.polo, self.competencia), 15)

    def test_tipos_diferentes_independentes_de_nome_e_codigo(self):
        self.quantidade.nome = 'Livros retirados'
        self.livros.nome = 'Quantidade de atendimentos'
        self.assertEqual(self.calcular(self.quantidade, self.polo, self.competencia), 3)
        self.assertEqual(self.calcular(self.livros, self.polo, self.competencia), 15)

    def test_sem_atendimentos_retorna_zero(self):
        for indicador in [self.quantidade, self.livros]:
            self.assertEqual(self.calcular(indicador, self.polo, date(2027, 1, 1)), 0)

    def test_ano_conta_e_soma_apenas_polo_e_ano_selecionados(self):
        self.assertEqual(self.calcular(self.quantidade, self.polo, self.competencia, anual=True), 5)
        self.assertEqual(self.calcular(self.livros, self.polo, self.competencia, anual=True), 65)

    def test_fevereiro_bissexto_e_dia_da_competencia(self):
        Atendimento.objects.create(polo=self.polo, data=date(2024, 2, 29), livros_retirados=7)
        Atendimento.objects.create(polo=self.polo, data=date(2024, 3, 1), livros_retirados=50)
        self.assertEqual(self.calcular(self.livros, self.polo, date(2024, 2, 12)), 7)

    def test_percentual_50(self):
        self.assertEqual(self.percentual(50, Decimal('100')), Decimal('50'))

    def test_percentual_130_sem_teto(self):
        self.assertEqual(self.percentual(130, Decimal('100')), Decimal('130'))

    def test_percentual_zero_realizado_e_meta_positiva(self):
        self.assertEqual(self.percentual(0, Decimal('100')), Decimal('0'))

    def test_percentual_neutro_meta_zero_ausente_ou_calculo_pendente(self):
        for realizado, previsto in [(15, 0), (0, 0), (15, None), (None, 100)]:
            self.assertIsNone(self.percentual(realizado, previsto))

    def test_previsoes_e_percentuais_mensais_anuais_no_servico(self):
        MetaMensal.objects.create(polo=self.polo, indicador=self.quantidade, competencia=self.competencia, previsto=2)
        MetaMensal.objects.create(polo=self.polo, indicador=self.quantidade, competencia=date(2026, 11, 1), previsto=8)
        MetaMensal.objects.create(polo=self.outro, indicador=self.quantidade, competencia=self.competencia, previsto=999)
        MetaMensal.objects.create(polo=self.polo, indicador=self.livros, competencia=self.competencia, previsto=30)
        MetaMensal.objects.create(polo=self.polo, indicador=self.quantidade, competencia=date(2025, 10, 1), previsto=999)
        resultados, _ = self.resultados(self.competencia, [self.quantidade, self.livros], [self.polo.pk])
        qtd, livros = resultados[self.polo.pk]
        self.assertEqual(qtd['mensal'], Decimal('2'))
        self.assertEqual(qtd['realizado'], 3)
        self.assertEqual(qtd['atingimento'], Decimal('150'))
        self.assertEqual(qtd['anual'], Decimal('10'))
        self.assertEqual(qtd['realizado_anual'], 5)
        self.assertEqual(qtd['atingimento_anual'], Decimal('50'))
        self.assertEqual(livros['realizado'], 15)
        self.assertEqual(livros['atingimento'], Decimal('50'))

    def test_meta_ausente_nao_oculta_realizado(self):
        resultados, _ = self.resultados(self.competencia, [self.quantidade], [self.polo.pk])
        item = resultados[self.polo.pk][0]
        self.assertIsNone(item['mensal'])
        self.assertEqual(item['realizado'], 3)
        self.assertIsNone(item['atingimento'])

    def test_novo_indicador_exige_tipo_no_orm_e_admin(self):
        with self.assertRaises(ValidationError):
            Indicador.objects.create(codigo='novo', nome='Novo')
        from django.forms import modelform_factory
        form_class = modelform_factory(Indicador, fields=['codigo', 'nome', 'tipo_calculo', 'ativo'])
        form = form_class(data={'codigo': 'novo', 'nome': 'Novo', 'ativo': True})
        self.assertFalse(form.is_valid())
        self.assertIn('tipo_calculo', form.errors)

    def test_tipo_invalido_rejeitado(self):
        self.quantidade.tipo_calculo = 'invalido'
        with self.assertRaises(ValidationError):
            self.calcular(self.quantidade, self.polo, self.competencia)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Indicador.objects.filter(pk=self.quantidade.pk).update(tipo_calculo='invalido')

    def test_indicador_legado_pendente_nao_recebe_regra_inventada(self):
        Indicador.objects.filter(pk=self.quantidade.pk).update(tipo_calculo=None)
        self.quantidade.refresh_from_db()
        self.assertIsNone(self.calcular(self.quantidade, self.polo, self.competencia))
        resultados, _ = self.resultados(self.competencia, [self.quantidade], [self.polo.pk])
        self.assertIsNone(resultados[self.polo.pk][0]['realizado'])
        response = self.client.get('/', {'unit': self.polo.pk, 'month': '2026-10'})
        self.assertContains(response, 'Tipo de calculo pendente'.replace('calculo', 'c\u00e1lculo'))

    def test_calculo_em_lote_equivale_a_funcao_individual_sem_n_mais_um(self):
        with self.assertNumQueries(2):
            resultados, _ = self.resultados(self.competencia, [self.quantidade, self.livros], [self.polo.pk, self.outro.pk])
        for polo in [self.polo, self.outro]:
            for item in resultados[polo.pk]:
                self.assertEqual(item['realizado'], self.calcular(item['indicador'], polo, self.competencia))
                self.assertEqual(item['realizado_anual'], self.calcular(item['indicador'], polo, self.competencia, anual=True))

    def test_home_e_records_exibem_metricas_e_percentual(self):
        MetaMensal.objects.create(polo=self.polo, indicador=self.quantidade, competencia=self.competencia, previsto=2)
        for url in ['/', '/registros/']:
            response = self.client.get(url, {'unit': self.polo.pk, 'month': '2026-10'})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '150,00%')
            self.assertContains(response, 'Realizado')
            self.assertNotContains(response, 'Realizado anual')


from django.test import TransactionTestCase


class MigrationTipoCalculoTests(TransactionTestCase):
    def test_migration_preserva_indicadores_e_metas_sem_inventar_tipo(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        anterior = [('portal', '0004_estrutura_normalizada')]
        atual = [('portal', '0005_indicador_tipo_calculo')]
        executor = MigrationExecutor(connection)
        executor.migrate(anterior)
        try:
            apps = executor.loader.project_state(anterior).apps
            indicador = apps.get_model('portal', 'Indicador').objects.create(codigo='legado', nome='Indicador legado')
            polo = apps.get_model('portal', 'Polo').objects.create(nome='Polo legado de teste')
            meta = apps.get_model('portal', 'MetaMensal').objects.create(polo=polo, indicador=indicador, competencia=date(2026, 10, 1), previsto=100)
            executor = MigrationExecutor(connection)
            executor.migrate(atual)
            apps = executor.loader.project_state(atual).apps
            preservado = apps.get_model('portal', 'Indicador').objects.get(pk=indicador.pk)
            self.assertEqual(preservado.nome, 'Indicador legado')
            self.assertIsNone(preservado.tipo_calculo)
            self.assertTrue(apps.get_model('portal', 'MetaMensal').objects.filter(pk=meta.pk, previsto=100).exists())
        finally:
            MigrationExecutor(connection).migrate([('portal', '0006_perfilusuario')])

class CadastroAtendimentoTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser(username='test-access', password='test-pass'))
        self.polo = Polo.objects.create(nome='Polo operacional')
        self.outro = Polo.objects.create(nome='Outro polo operacional')
        self.inativo = Polo.objects.create(nome='Polo inativo', ativo=False)
        self.evento = Evento.objects.create(polo=self.polo, titulo='Evento local', data_inicio=date(2026, 10, 1), data_fim=date(2026, 10, 2))
        self.outro_evento = Evento.objects.create(polo=self.outro, titulo='Evento de outro polo', data_inicio=date(2026, 10, 1), data_fim=date(2026, 10, 2))
        self.url = '/atendimentos/novo/'

    def dados(self, **kwargs):
        return {'polo': self.polo.pk, 'data': '2026-10-14', 'livros_retirados': 5,
                'observacao': 'Observacao registrada pelo formulario', **kwargs}

    def test_get_campos_ativos_data_html_e_csrf(self):
        response = self.client.get(self.url, {'unit': self.polo.pk})
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(set(form.Meta.fields), {'polo', 'data', 'livros_retirados', 'observacao', 'evento'})
        self.assertEqual(form.initial['polo'], str(self.polo.pk))
        self.assertIn(self.polo, form.fields['polo'].queryset)
        self.assertNotIn(self.inativo, form.fields['polo'].queryset)
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'type="date"')
        self.assertContains(response, date.today().isoformat())

    def test_post_salva_um_registro_com_dados_e_redirect_para_polo_mes(self):
        response = self.client.post(self.url, self.dados())
        self.assertRedirects(response, f'/?unit={self.polo.pk}&month=2026-10')
        self.assertEqual(Atendimento.objects.count(), 1)
        atendimento = Atendimento.objects.get()
        self.assertEqual(atendimento.polo, self.polo)
        self.assertEqual(atendimento.data, date(2026, 10, 14))
        self.assertEqual(atendimento.livros_retirados, 5)
        self.assertEqual(atendimento.observacao, self.dados()['observacao'])
        self.assertIsNone(atendimento.evento)
        self.assertIsNone(atendimento.legacy_sharepoint_id)

    def test_mensagem_sucesso_e_refresh_nao_duplica(self):
        response = self.client.post(self.url, self.dados(), follow=True)
        self.assertContains(response, 'Atendimento registrado com sucesso.')
        destino = response.redirect_chain[0][0]
        response = self.client.get(destino)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Atendimento registrado com sucesso.')
        self.assertEqual(Atendimento.objects.count(), 1)

    def test_evento_mesmo_polo_aceito(self):
        response = self.client.post(self.url, self.dados(evento=self.evento.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Atendimento.objects.get().evento, self.evento)

    def test_evento_outro_polo_rejeitado(self):
        response = self.client.post(self.url, self.dados(evento=self.outro_evento.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn('evento', response.context['form'].errors)
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_polo_ausente_inexistente_e_inativo_rejeitados(self):
        for polo in ['', 999999, self.inativo.pk, 'invalido']:
            with self.subTest(polo=polo):
                response = self.client.post(self.url, self.dados(polo=polo))
                self.assertEqual(response.status_code, 200)
                self.assertIn('polo', response.context['form'].errors)
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_data_invalida_rejeitada_sem_restricao_de_periodo(self):
        for valor in ['', '2026-02-30', 'data-invalida']:
            with self.subTest(data=valor):
                response = self.client.post(self.url, self.dados(data=valor))
                self.assertIn('data', response.context['form'].errors)
        self.assertEqual(Atendimento.objects.count(), 0)
        for valor in ['2020-01-01', '2030-01-01']:
            self.assertEqual(self.client.post(self.url, self.dados(data=valor)).status_code, 302)

    def test_livros_negativos_fracionarios_e_nao_numericos_rejeitados(self):
        for valor in [-1, '1.5', 'abc', '']:
            with self.subTest(livros=valor):
                response = self.client.post(self.url, self.dados(livros_retirados=valor))
                self.assertEqual(response.status_code, 200)
                self.assertIn('livros_retirados', response.context['form'].errors)
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_zero_livros_e_observacao_vazia_aceitos(self):
        self.assertEqual(self.client.post(self.url, self.dados(livros_retirados=0, observacao='')).status_code, 302)
        atendimento = Atendimento.objects.get()
        self.assertEqual(atendimento.livros_retirados, 0)
        self.assertEqual(atendimento.observacao, '')

    def test_erros_preservam_dados_e_limite_observacao(self):
        response = self.client.post(self.url, self.dados(livros_retirados=-1))
        self.assertContains(response, self.dados()['observacao'])
        self.assertContains(response, '2026-10-14')
        self.assertContains(response, 'value="-1"')
        self.assertTrue(response.context['form'].is_bound)
        response = self.client.post(self.url, self.dados(observacao='x' * 2001))
        self.assertIn('observacao', response.context['form'].errors)
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_dois_atendimentos_no_mesmo_dia_e_calculos_sem_alterar_metas(self):
        from .services.indicadores import calcular_realizado
        qtd = Indicador.objects.create(codigo='operacao-qtd', nome='Quantidade', tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS)
        livros = Indicador.objects.create(codigo='operacao-livros', nome='Livros', tipo_calculo=Indicador.TipoCalculo.LIVROS_RETIRADOS)
        meta = MetaMensal.objects.create(polo=self.polo, indicador=qtd, competencia=date(2026, 10, 1), previsto=100)
        for valor in [5, 8]:
            self.assertEqual(self.client.post(self.url, self.dados(livros_retirados=valor)).status_code, 302)
        self.assertEqual(Atendimento.objects.count(), 2)
        self.assertEqual(calcular_realizado(qtd, self.polo, date(2026, 10, 1)), 2)
        self.assertEqual(calcular_realizado(livros, self.polo, date(2026, 10, 1)), 13)
        self.assertEqual(calcular_realizado(qtd, self.outro, date(2026, 10, 1)), 0)
        self.assertEqual(calcular_realizado(livros, self.outro, date(2026, 10, 1)), 0)
        meta.refresh_from_db()
        self.assertEqual(meta.previsto, Decimal('100'))
        home = self.client.get('/', {'unit': self.polo.pk, 'month': '2026-10'})
        self.assertEqual(home.context['totals'], {'completed': 2, 'livros': 13})
        registros = self.client.get('/registros/?month=2026-10')
        row = next(item for item in registros.context['rows'] if item['name'] == self.polo.nome)
        self.assertEqual((row['completed'], row['livros']), (2, 13))

    def test_csrf_rejeita_post_sem_token(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, self.dados()).status_code, 403)
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_admin_atendimento_continua_cadastrando(self):
        from django.contrib.auth import get_user_model
        usuario = get_user_model().objects.create_superuser(username='admin-operacao', password='senha-so-no-teste')
        self.client.force_login(usuario)
        response = self.client.post('/admin/portal/atendimento/add/', {**self.dados(), '_save': 'Salvar'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Atendimento.objects.count(), 1)

from django.test import LiveServerTestCase


class CadastroAtendimentoHTTPTests(LiveServerTestCase):
    def test_fluxo_http_com_csrf_sucesso_refresh_e_indicadores(self):
        import re
        from urllib.parse import urlencode
        from urllib.request import build_opener, HTTPCookieProcessor
        from http.cookiejar import CookieJar
        from .services.indicadores import calcular_realizado
        polo = Polo.objects.create(nome='Polo HTTP de teste')
        indicador = Indicador.objects.create(codigo='http-qtd', nome='Quantidade HTTP', tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS)
        livros = Indicador.objects.create(codigo='http-livros', nome='Livros HTTP', tipo_calculo=Indicador.TipoCalculo.LIVROS_RETIRADOS)
        navegador = build_opener(HTTPCookieProcessor(CookieJar()))
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_superuser(username='http-admin', password='http-test-pass')
        login_url = self.live_server_url + '/login/'
        with navegador.open(login_url, timeout=10) as response:
            login_html = response.read().decode('utf-8')
        login_token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_html).group(1)
        with navegador.open(login_url, data=urlencode({'username': 'http-admin', 'password': 'http-test-pass', 'csrfmiddlewaretoken': login_token}).encode(), timeout=10) as response:
            self.assertEqual(response.status, 200)
        formulario = self.live_server_url + '/atendimentos/novo/'
        with navegador.open(formulario, timeout=10) as response:
            html = response.read().decode('utf-8')
            self.assertEqual(response.status, 200)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
        dados = urlencode({'csrfmiddlewaretoken': token, 'polo': polo.pk, 'data': '2026-10-14',
                           'livros_retirados': 5, 'observacao': 'Fluxo HTTP real em banco de teste'}).encode()
        with navegador.open(formulario, data=dados, timeout=10) as response:
            html = response.read().decode('utf-8')
            destino = response.url
            self.assertEqual(response.status, 200)
        self.assertIn(f'/?unit={polo.pk}&month=2026-10', destino)
        self.assertIn('Atendimento registrado com sucesso.', html)
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(calcular_realizado(indicador, polo, date(2026, 10, 1)), 1)
        self.assertEqual(calcular_realizado(livros, polo, date(2026, 10, 1)), 5)
        with navegador.open(destino, timeout=10) as response:
            self.assertEqual(response.status, 200)
        with navegador.open(self.live_server_url + '/registros/?month=2026-10', timeout=10) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(polo.nome, response.read().decode('utf-8'))
        self.assertEqual(Atendimento.objects.count(), 1)

class SeedPolosTests(TestCase):
    def executar(self):
        from io import StringIO
        from django.core.management import call_command
        output = StringIO()
        call_command('seed_polos', stdout=output)
        return output.getvalue()

    def test_banco_vazio_cria_26_nomes_exatos_e_parceiros(self):
        from portal.management.commands.seed_polos import POLOS
        output = self.executar()
        self.assertEqual(Polo.objects.count(), 26)
        self.assertEqual(Polo.objects.filter(parceiro='SENAI').count(), 2)
        self.assertEqual(Polo.objects.filter(parceiro='Prefeitura').count(), 24)
        self.assertEqual(set(Polo.objects.values_list('nome', 'parceiro')), set(POLOS))
        self.assertIn('Criados: 26', output)
        self.assertIn('Atualizados: 0', output)
        self.assertIn('Total processado: 26', output)

    def test_parceiros_acailandia_caxias_estreito(self):
        self.executar()
        self.assertEqual(Polo.objects.get(nome='A\u00e7ail\u00e2ndia').parceiro, 'SENAI')
        self.assertEqual(Polo.objects.get(nome='Caxias').parceiro, 'SENAI')
        self.assertEqual(Polo.objects.get(nome='Estreito').parceiro, 'Prefeitura')

    def test_reexecucao_idempotente(self):
        self.executar()
        before = list(Polo.objects.order_by('pk').values())
        output = self.executar()
        self.assertEqual(list(Polo.objects.order_by('pk').values()), before)
        self.assertIn('Criados: 0', output)
        self.assertIn('Atualizados: 0', output)
        self.assertIn('J\u00e1 corretos: 26', output)

    def test_atualiza_so_parceiro_preservando_campos_e_relacoes(self):
        polo = Polo.objects.create(nome='A\u00e7ail\u00e2ndia', parceiro='Antigo', ativo=False,
                                   telefone='telefone de teste', foto='polos/foto-teste.jpg',
                                   latitude=Decimal('-2.123456'), longitude=Decimal('-44.123456'),
                                   horario_funcionamento='horario de teste', legacy_sharepoint_id=123)
        responsavel = ResponsavelPolo.objects.create(polo=polo, nome='Responsavel de teste')
        atendimento = Atendimento.objects.create(polo=polo, data=date(2026, 10, 14))
        before = Polo.objects.values().get(pk=polo.pk)
        output = self.executar()
        after = Polo.objects.values().get(pk=polo.pk)
        self.assertEqual(after, {**before, 'parceiro': 'SENAI'})
        self.assertTrue(ResponsavelPolo.objects.filter(pk=responsavel.pk, polo=polo).exists())
        self.assertTrue(Atendimento.objects.filter(pk=atendimento.pk, polo=polo).exists())
        self.assertIn('Atualizados: 1', output)
        self.assertIn('Criados: 25', output)

    def test_unicode_casefold_evitar_duplicidade_sem_renomear(self):
        polo = Polo.objects.create(nome='A\u00c7AIL\u00c2NDIA', parceiro='Antigo')
        self.executar()
        polo.refresh_from_db()
        self.assertEqual(polo.nome, 'A\u00c7AIL\u00c2NDIA')
        self.assertEqual(polo.parceiro, 'SENAI')
        self.assertEqual(Polo.objects.count(), 26)
        self.assertFalse(Polo.objects.filter(nome='A\u00e7ail\u00e2ndia').exists())

    def test_campos_nao_fornecidos_usam_apenas_defaults(self):
        self.executar()
        self.assertFalse(Polo.objects.exclude(legacy_sharepoint_id=None).exists())
        for polo in Polo.objects.all():
            self.assertTrue(polo.ativo)
            self.assertEqual(polo.telefone, '')
            self.assertEqual(polo.horario_funcionamento, '')
            self.assertFalse(polo.foto)
            self.assertIsNone(polo.latitude)
            self.assertIsNone(polo.longitude)
        for model in [ResponsavelPolo, Atendimento, Evento, Indicador, MetaMensal, AnexoAtendimento, AnexoEvento]:
            self.assertEqual(model.objects.count(), 0)

    def test_outro_polo_preexistente_preservado(self):
        polo = Polo.objects.create(nome='Polo fora da lista', parceiro='Parceiro anterior')
        self.executar()
        self.assertEqual(Polo.objects.count(), 27)
        polo.refresh_from_db()
        self.assertEqual(polo.parceiro, 'Parceiro anterior')

    def test_nomes_ambiguos_interrompem_sem_mutacao(self):
        from django.core.management.base import CommandError
        Polo.objects.create(nome='Estreito', parceiro='Antigo')
        Polo.objects.create(nome='ESTREITO', parceiro='Outro')
        before = list(Polo.objects.order_by('pk').values())
        with self.assertRaises(CommandError):
            self.executar()
        self.assertEqual(list(Polo.objects.order_by('pk').values()), before)

    def test_falha_no_meio_da_carga_reverte_criacoes_e_atualizacoes(self):
        from unittest.mock import patch
        from django.core.management.base import CommandError
        from django.core.exceptions import ValidationError
        polo = Polo.objects.create(nome='A\u00e7ail\u00e2ndia', parceiro='Antigo')
        original = Polo.save
        def falhar(instance, *args, **kwargs):
            if instance.nome == 'Pastos Bons':
                raise ValidationError('Erro simulado')
            return original(instance, *args, **kwargs)
        with patch.object(Polo, 'save', falhar), self.assertRaises(CommandError):
            self.executar()
        self.assertEqual(Polo.objects.count(), 1)
        polo.refresh_from_db()
        self.assertEqual(polo.parceiro, 'Antigo')
