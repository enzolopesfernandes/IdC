from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name='Attendance', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('unit', models.CharField(choices=[('acailandia', 'Açailândia'), ('bacabal', 'Bacabal'), ('caxias', 'Caxias'), ('imperatriz', 'Imperatriz'), ('sao-luis', 'São Luís')], max_length=30)), ('date', models.DateField()), ('expected', models.PositiveIntegerField(default=0)), ('completed', models.PositiveIntegerField(default=0)), ('notes', models.TextField(blank=True, max_length=2000))], options={'ordering': ['-date', 'unit']})]
