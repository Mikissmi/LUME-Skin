import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import RegraAtivos


class Command(BaseCommand):
    help = 'Importa o CSV de regras (perfil -> ativos recomendados)'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)

    def handle(self, *args, **options):
        try:
            # utf-8-sig remove o caractere invisível que o Excel coloca no início
            arquivo = open(options['csv_path'], encoding='utf-8-sig', newline='')
        except FileNotFoundError:
            raise CommandError(f"Arquivo não encontrado: {options['csv_path']}")

        objs = []
        with arquivo:
            for numero, r in enumerate(csv.DictReader(arquivo), start=2):
                try:
                    objs.append(RegraAtivos(
                        faixa_etaria=r['Faixa_Etária'].strip(),
                        tipo_pele=r['Tipo_de_Pele'].strip().lower(),   # 'Normal' -> 'normal'
                        subtipo=r['Subtipo_de_Pele'].strip(),
                        sensivel=r['Sensibilidade'].strip() == 'Sim',
                        preocupacao=r['Preocupação'].strip(),
                        tipo_interno=r['Tipo_Interno'].strip(),
                        ingredientes=r['Ingredientes'].strip(),
                        concentracoes=r['Concentrações'].strip(),
                        efeitos=r['Efeitos'].strip(),
                    ))
                except KeyError as erro:
                    raise CommandError(f'Coluna não encontrada na linha {numero}: {erro}')

        # só apaga as regras antigas depois de ler o arquivo inteiro sem erro
        with transaction.atomic():
            RegraAtivos.objects.all().delete()
            RegraAtivos.objects.bulk_create(objs, batch_size=500)

        self.stdout.write(self.style.SUCCESS(f'{len(objs)} regras importadas.'))