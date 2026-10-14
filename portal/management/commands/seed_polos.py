from collections import defaultdict

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portal.models import Polo


POLOS = (
    ('Açailândia', 'SENAI'),
    ('Estreito', 'Prefeitura'),
    ('São Raimundo das Mangabeiras', 'Prefeitura'),
    ('São Domingos do Azeitão', 'Prefeitura'),
    ('Pastos Bons', 'Prefeitura'),
    ('Sucupira do Norte', 'Prefeitura'),
    ('Grajaú', 'Prefeitura'),
    ('Lago da Pedra', 'Prefeitura'),
    ('Tuntum', 'Prefeitura'),
    ('Aldeias Altas', 'Prefeitura'),
    ('Buriti Bravo', 'Prefeitura'),
    ('Caxias', 'SENAI'),
    ('Codó', 'Prefeitura'),
    ('Colinas', 'Prefeitura'),
    ('Timon', 'Prefeitura'),
    ('Paraibano', 'Prefeitura'),
    ('Passagem Franca', 'Prefeitura'),
    ('Bacabeira', 'Prefeitura'),
    ('Barreirinhas', 'Prefeitura'),
    ('Icatu', 'Prefeitura'),
    ('Itapecuru-Mirim', 'Prefeitura'),
    ('Matões do Norte', 'Prefeitura'),
    ('Morros', 'Prefeitura'),
    ('Paço do Lumiar', 'Prefeitura'),
    ('Rosário', 'Prefeitura'),
    ('Santa Rita', 'Prefeitura'),
)


class Command(BaseCommand):
    help = 'Carga manual e idempotente dos 26 polos fornecidos: somente nome e parceiro.'

    def handle(self, *args, **options):
        criados = atualizados = corretos = 0
        try:
            with transaction.atomic():
                existentes = defaultdict(list)
                for polo in Polo.objects.select_for_update().all():
                    # casefold trata também letras acentuadas, ao contrário do
                    # iexact padrão do SQLite. Não modifica a grafia armazenada.
                    existentes[polo.nome.casefold()].append(polo)
                for nome, _ in POLOS:
                    if len(existentes[nome.casefold()]) > 1:
                        raise CommandError(f'Nome ambíguo: {nome}. Resolva os polos duplicados antes da carga.')
                for nome, parceiro in POLOS:
                    encontrados = existentes[nome.casefold()]
                    if not encontrados:
                        polo = Polo(nome=nome, parceiro=parceiro)
                        polo.full_clean()
                        polo.save()
                        criados += 1
                    elif encontrados[0].parceiro != parceiro:
                        # Altera exclusivamente parceiro, inclusive preservando
                        # atualizado_em e todos os dados/relações preexistentes.
                        Polo.objects.filter(pk=encontrados[0].pk).update(parceiro=parceiro)
                        atualizados += 1
                    else:
                        corretos += 1
        except ValidationError as error:
            raise CommandError(f'Carga cancelada por validação; nenhuma alteração aplicada: {error}') from error

        self.stdout.write(self.style.SUCCESS('Carga de Polos concluída.'))
        self.stdout.write(f'Criados: {criados}')
        self.stdout.write(f'Atualizados: {atualizados}')
        self.stdout.write(f'Já corretos: {corretos}')
        self.stdout.write(f'Total processado: {len(POLOS)}')
