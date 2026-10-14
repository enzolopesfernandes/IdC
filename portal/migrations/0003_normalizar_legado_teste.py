from django.db import migrations


def remover_registros_de_teste(apps, schema_editor):
    Attendance = apps.get_model('portal', 'Attendance')
    Attachment = apps.get_model('portal', 'Attachment')
    alias = schema_editor.connection.alias
    # O usuário confirmou que os registros existentes são exclusivamente de teste.
    # Não converter quantidades agregadas em atendimentos individuais.
    if Attachment.objects.using(alias).exists():
        raise RuntimeError('Existem anexos legados: revise os dados antes da normalização.')
    if Attendance.objects.using(alias).count() > 2:
        raise RuntimeError('Há mais de dois registros legados: revise os dados antes da normalização.')
    Attendance.objects.using(alias).all().delete()


class Migration(migrations.Migration):
    dependencies = [('portal', '0002_attachment')]
    operations = [
        migrations.RunPython(remover_registros_de_teste),
        migrations.RenameModel('Attendance', 'Atendimento'),
        migrations.RenameModel('Attachment', 'AnexoAtendimento'),
        migrations.RenameField('atendimento', 'date', 'data'),
        migrations.RenameField('atendimento', 'notes', 'observacao'),
        migrations.RenameField('anexoatendimento', 'attendance', 'atendimento'),
        migrations.RenameField('anexoatendimento', 'file', 'arquivo'),
        migrations.RenameField('anexoatendimento', 'name', 'nome_original'),
        migrations.RemoveField('atendimento', 'unit'),
        migrations.RemoveField('atendimento', 'expected'),
        migrations.RemoveField('atendimento', 'completed'),
    ]
