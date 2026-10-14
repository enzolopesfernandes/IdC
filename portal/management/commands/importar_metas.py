import csv
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portal.models import Indicador, MetaMensal, Polo


COLUNAS = ('ChaveMeta', 'Polo', 'Mes_Referencia', 'Indicador', 'Valor')


def erro_linha(linha, chave, motivo):
    return CommandError(f'Linha {linha}, ChaveMeta {chave or "(ausente)"}: {motivo}')


def ler_csv(caminho):
    registros, chaves, combinacoes = [], set(), set()
    try:
        with caminho.open(encoding='utf-8-sig', newline='') as arquivo:
            leitor = csv.DictReader(arquivo, strict=True)
            campos = leitor.fieldnames or []
            if not set(COLUNAS).issubset(campos) or len(campos) != len(set(campos)):
                raise CommandError('Linha 1: cabeçalho inválido. Colunas obrigatórias: ' + ', '.join(COLUNAS))
            for row in leitor:
                linha = leitor.line_num
                chave = (row.get('ChaveMeta') or '').strip()
                if None in row or any(row.get(campo) is None for campo in COLUNAS):
                    raise erro_linha(linha, chave, 'quantidade de campos inválida.')
                valores = {campo: row[campo].strip() for campo in COLUNAS}
                for campo in COLUNAS:
                    if not valores[campo]:
                        raise erro_linha(linha, chave, f'{campo} não pode ficar vazio.')
                if valores['Indicador'] != 'Atendimentos':
                    raise erro_linha(linha, chave, 'indicador não suportado; esperado Atendimentos.')
                data = valores['Mes_Referencia']
                try:
                    if not re.fullmatch(r'[0-9]{2}/[0-9]{2}/[0-9]{4}', data):
                        raise ValueError
                    competencia = datetime.strptime(data, '%d/%m/%Y').date()
                    if competencia.day != 1 or competencia.year != 2026:
                        raise ValueError
                except ValueError:
                    raise erro_linha(linha, chave, 'Mes_Referencia deve ser uma data válida no primeiro dia do mês de 2026.')
                texto = valores['Valor']
                if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)', texto):
                    raise erro_linha(linha, chave, 'Valor deve ser inteiro não negativo; ponto é separador de milhar (1.800 = 1800).')
                previsto = Decimal(texto.replace('.', ''))
                try:
                    MetaMensal._meta.get_field('previsto').clean(previsto, None)
                except ValidationError as error:
                    raise erro_linha(linha, chave, f'Valor fora dos limites do model: {error}') from error
                combinacao = (valores['Polo'].casefold(), competencia)
                if chave in chaves:
                    raise erro_linha(linha, chave, 'ChaveMeta duplicada.')
                if combinacao in combinacoes:
                    raise erro_linha(linha, chave, 'Polo + Indicador + Competência duplicados.')
                chaves.add(chave)
                combinacoes.add(combinacao)
                registros.append({'linha': linha, 'chave': chave, 'nome': valores['Polo'],
                                  'competencia': competencia, 'previsto': previsto})
    except (OSError, UnicodeError, csv.Error) as error:
        numero = leitor.line_num if 'leitor' in locals() else 1
        raise CommandError(f'Erro de leitura na linha {numero}: {error}') from error
    if not registros:
        raise CommandError('Arquivo sem registros de metas.')
    return registros


def validar_cadastros(registros):
    polos = defaultdict(list)
    for polo in Polo.objects.all():
        polos[polo.nome.casefold()].append(polo)
    faltantes = []
    for registro in registros:
        candidatos = polos[registro['nome'].casefold()]
        if not candidatos:
            faltantes.append(f"linha {registro['linha']}, ChaveMeta {registro['chave']}: {registro['nome']}")
        elif len(candidatos) > 1:
            raise erro_linha(registro['linha'], registro['chave'], f"Polo ambíguo: {registro['nome']}.")
        else:
            registro['polo'] = candidatos[0]
    if faltantes:
        raise CommandError('Polos ausentes; nenhuma gravação realizada:\n' + '\n'.join(faltantes))
    indicadores = list(Indicador.objects.all())
    candidatos = [item for item in indicadores if item.codigo.casefold() == 'atendimentos']
    if not candidatos:
        candidatos = [item for item in indicadores if item.nome.casefold() == 'atendimentos']
    if len(candidatos) > 1:
        raise CommandError('Indicador Atendimentos ambíguo; nenhuma gravação realizada.')
    indicador = candidatos[0] if candidatos else None
    if indicador and indicador.tipo_calculo != Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS:
        raise CommandError(f'Conflito no indicador {indicador.codigo}: tipo_calculo={indicador.tipo_calculo!r}; esperado quantidade_atendimentos. Nenhuma gravação realizada.')
    return indicador


def planejar(registros, indicador):
    existentes = {
        (meta.polo_id, meta.competencia): meta for meta in MetaMensal.objects.filter(
            indicador=indicador, polo_id__in={row['polo'].pk for row in registros}, competencia__year=2026,
        )
    } if indicador else {}
    plano = []
    for registro in registros:
        meta = existentes.get((registro['polo'].pk, registro['competencia']))
        acao = 'criadas' if meta is None else ('atualizadas' if meta.previsto != registro['previsto'] else 'inalteradas')
        plano.append((registro, meta, acao))
    return plano


class Command(BaseCommand):
    help = 'Importa metas de Atendimentos de 2026 de um CSV manual, com validação e idempotência.'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', type=Path)
        parser.add_argument('--dry-run', action='store_true', help='Valida e prevê alterações sem gravar.')

    def handle(self, *args, **options):
        registros = ler_csv(options['arquivo'])
        indicador = validar_cadastros(registros)
        plano = planejar(registros, indicador)
        if not options['dry_run']:
            try:
                with transaction.atomic():
                    # Repete a checagem antes de gravar para não confiar em um
                    # plano calculado antes de alterações de outro processo.
                    indicador = validar_cadastros(registros)
                    plano = planejar(registros, indicador)
                    if indicador is None:
                        indicador = Indicador(codigo='atendimentos', nome='Atendimentos',
                                              tipo_calculo=Indicador.TipoCalculo.QUANTIDADE_ATENDIMENTOS, ativo=True)
                        indicador.full_clean()
                        indicador.save()
                    for registro, meta, acao in plano:
                        if acao == 'criadas':
                            meta = MetaMensal(polo=registro['polo'], indicador=indicador,
                                             competencia=registro['competencia'], previsto=registro['previsto'])
                            meta.full_clean()
                            meta.save()
                        elif acao == 'atualizadas':
                            meta.previsto = registro['previsto']
                            meta.full_clean()
                            meta.save(update_fields=['previsto'])
            except ValidationError as error:
                raise CommandError(f'Importação revertida por validação: {error}') from error
        contagens = {acao: sum(item[2] == acao for item in plano) for acao in ['criadas', 'atualizadas', 'inalteradas']}
        self.stdout.write(self.style.SUCCESS('Prévia validada; nenhuma gravação realizada.' if options['dry_run'] else 'Importação de metas concluída.'))
        self.stdout.write(f"Arquivo: {options['arquivo']}")
        self.stdout.write(f'Linhas processadas: {len(registros)}')
        self.stdout.write(f"Criadas: {contagens['criadas']}\nAtualizadas: {contagens['atualizadas']}\nSem alteração: {contagens['inalteradas']}\nErros: 0")
        self.stdout.write(f"Indicador: Atendimentos\nPolos processados: {len({row['polo'].pk for row in registros})}")
