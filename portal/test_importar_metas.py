import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from django.test import TestCase

from .models import Polo, Indicador, MetaMensal
from .management.commands.importar_metas import COLUNAS


class ImportarMetasTests(TestCase):
    def setUp(self):
        self.polo = Polo.objects.create(nome='A\u00e7ail\u00e2ndia', parceiro='SENAI')
        self.outro = Polo.objects.create(nome='Polo sem meta')
        self.rows = [['chave-1', self.polo.nome, '01/01/2026', 'Atendimentos', '1.800']]

    def executar(self, rows=None, dry_run=False, header=COLUNAS):
        with TemporaryDirectory(dir='.') as directory:
            path = Path(directory) / 'metas.csv'
            with path.open('w', encoding='utf-8-sig', newline='') as arquivo:
                writer = csv.writer(arquivo)
                writer.writerow(header)
                writer.writerows(self.rows if rows is None else rows)
            output = StringIO()
            call_command('importar_metas', str(path), dry_run=dry_run, stdout=output)
            return output.getvalue()

    def test_csv_valido_valor_milhar_e_indicador_correto(self):
        output = self.executar()
        meta = MetaMensal.objects.get()
        self.assertEqual(meta.previsto, Decimal('1800'))
        self.assertEqual(meta.competencia, date(2026, 1, 1))
        self.assertEqual(meta.indicador.codigo, 'atendimentos')
        self.assertEqual(meta.indicador.tipo_calculo, Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS)
        self.assertTrue(meta.indicador.ativo)
        self.assertIn('Criadas: 1', output)
        self.assertIsNone(self.polo.legacy_sharepoint_id)

    def test_doze_metas_soma_10230(self):
        valores = ['100', '450', '600', '1.800', '1.600', '1.600', '380', '1.000', '1.000', '1.200', '300', '200']
        rows = [[f'chave-{m}', self.polo.nome, f'01/{m:02}/2026', 'Atendimentos', valor] for m, valor in enumerate(valores, 1)]
        self.executar(rows)
        self.assertEqual(MetaMensal.objects.count(), 12)
        self.assertEqual(MetaMensal.objects.aggregate(total=Sum('previsto'))['total'], Decimal('10230'))

    def test_reexecucao_nao_duplica_nem_altera_timestamps(self):
        self.executar()
        before = list(MetaMensal.objects.values())
        output = self.executar()
        self.assertEqual(list(MetaMensal.objects.values()), before)
        self.assertEqual(Indicador.objects.count(), 1)
        self.assertIn('Sem altera\u00e7\u00e3o: 1', output)

    def test_valor_diferente_atualiza_so_previsto(self):
        self.executar()
        before = MetaMensal.objects.values().get()
        rows = [['chave-1', self.polo.nome, '01/01/2026', 'Atendimentos', '2.000']]
        output = self.executar(rows)
        self.assertEqual(MetaMensal.objects.values().get(), {**before, 'previsto': Decimal('2000')})
        self.assertIn('Atualizadas: 1', output)

    def test_polo_ausente_cancela_antes_de_criar_indicador(self):
        rows = self.rows + [['chave-2', 'Ausente', '01/02/2026', 'Atendimentos', '100']]
        with self.assertRaisesMessage(CommandError, 'Ausente'):
            self.executar(rows)
        self.assertEqual(MetaMensal.objects.count(), 0)
        self.assertEqual(Indicador.objects.count(), 0)
        self.assertEqual(Polo.objects.count(), 2)

    def test_valores_invalidos_rejeitados(self):
        for valor in ['', '-1', '1.8', '1,5', '1.80', '1.800.00', 'texto', '1000000000000']:
            with self.subTest(valor=valor), self.assertRaises(CommandError):
                self.executar([self.rows[0], ['chave-2', self.polo.nome, '01/02/2026', 'Atendimentos', valor]])
        self.assertEqual(MetaMensal.objects.count(), 0)
        self.assertEqual(Indicador.objects.count(), 0)

    def test_datas_invalidas_e_outro_ano_rejeitados(self):
        for data in ['31/02/2026', '02/01/2026', '01/01/2025', '2026-01-01', '1/1/2026', '']:
            with self.subTest(data=data), self.assertRaises(CommandError):
                self.executar([['chave', self.polo.nome, data, 'Atendimentos', '100']])
        self.assertEqual(MetaMensal.objects.count(), 0)

    def test_combinacao_duplicada_rejeitada(self):
        row = ['chave-2', self.polo.nome.upper(), '01/01/2026', 'Atendimentos', '100']
        with self.assertRaisesMessage(CommandError, 'duplicados'):
            self.executar(self.rows + [row])
        self.assertEqual(MetaMensal.objects.count(), 0)

    def test_chave_duplicada_rejeitada_com_linha(self):
        row = ['chave-1', self.polo.nome, '01/02/2026', 'Atendimentos', '100']
        with self.assertRaisesMessage(CommandError, 'Linha 3, ChaveMeta chave-1'):
            self.executar(self.rows + [row])

    def test_polo_fora_csv_nao_recebe_meta_zero(self):
        self.executar()
        self.assertFalse(MetaMensal.objects.filter(polo=self.outro).exists())

    def test_indicador_nao_suportado_rejeitado(self):
        with self.assertRaisesMessage(CommandError, 'indicador n\u00e3o suportado'):
            self.executar([['chave', self.polo.nome, '01/01/2026', 'Livros', '100']])
        self.assertEqual(Indicador.objects.count(), 0)

    def test_indicador_incompativel_ou_pendente_cancela(self):
        indicador = Indicador.objects.create(codigo='atendimentos', nome='Atendimentos', tipo_calculo=Indicador.TipoCalculo.LIVROS_RETIRADOS)
        with self.assertRaisesMessage(CommandError, 'Conflito'):
            self.executar()
        indicador.refresh_from_db()
        self.assertEqual(indicador.tipo_calculo, Indicador.TipoCalculo.LIVROS_RETIRADOS)
        Indicador.objects.filter(pk=indicador.pk).update(tipo_calculo=None)
        with self.assertRaisesMessage(CommandError, 'Conflito'):
            self.executar()
        self.assertEqual(MetaMensal.objects.count(), 0)

    def test_indicador_compativel_nome_existente_nao_duplica(self):
        indicador = Indicador.objects.create(codigo='codigo-anterior', nome='Atendimentos', ativo=False, tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS)
        self.executar()
        self.assertEqual(Indicador.objects.count(), 1)
        self.assertEqual(MetaMensal.objects.get().indicador, indicador)
        indicador.refresh_from_db()
        self.assertFalse(indicador.ativo)

    def test_dry_run_nao_grava_e_preve_acoes(self):
        output = self.executar(dry_run=True)
        self.assertIn('Criadas: 1', output)
        self.assertEqual(MetaMensal.objects.count(), 0)
        self.assertEqual(Indicador.objects.count(), 0)
        self.executar()
        before = list(MetaMensal.objects.values())
        output = self.executar([['chave', self.polo.nome, '01/01/2026', 'Atendimentos', '99']], dry_run=True)
        self.assertIn('Atualizadas: 1', output)
        self.assertEqual(list(MetaMensal.objects.values()), before)

    def test_cabecalho_campos_vazios_e_csv_vazio_rejeitados(self):
        with self.assertRaises(CommandError):
            self.executar([], header=['Polo'])
        with self.assertRaises(CommandError):
            self.executar([])
        for index in [0, 1, 3]:
            rows = [self.rows[0].copy()]
            rows[0][index] = ''
            with self.assertRaises(CommandError):
                self.executar(rows)

    def test_polo_ambiguo_rejeitado(self):
        Polo.objects.create(nome=self.polo.nome.upper())
        with self.assertRaisesMessage(CommandError, 'amb\u00edguo'):
            self.executar()

    def test_rollback_erro_durante_gravacao_reverte_indicador_e_metas(self):
        original = MetaMensal.save
        def falhar(meta, *args, **kwargs):
            if meta.competencia.month == 2:
                raise ValidationError('Erro simulado')
            return original(meta, *args, **kwargs)
        rows = self.rows + [['chave-2', self.polo.nome, '01/02/2026', 'Atendimentos', '100']]
        with patch.object(MetaMensal, 'save', falhar), self.assertRaises(CommandError):
            self.executar(rows)
        self.assertEqual(MetaMensal.objects.count(), 0)
        self.assertEqual(Indicador.objects.count(), 0)

    def test_zero_aceito_sem_alterar_polos(self):
        before = list(Polo.objects.order_by('pk').values())
        self.executar([['chave', self.polo.nome, '01/01/2026', 'Atendimentos', '0']])
        self.assertEqual(MetaMensal.objects.get().previsto, 0)
        self.assertEqual(list(Polo.objects.order_by('pk').values()), before)
