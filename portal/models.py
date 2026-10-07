from django.db import models

UNITS = [('acailandia', 'Açailândia'), ('bacabal', 'Bacabal'), ('caxias', 'Caxias'), ('imperatriz', 'Imperatriz'), ('sao-luis', 'São Luís')]


class Attendance(models.Model):
    unit = models.CharField(max_length=30, choices=UNITS)
    date = models.DateField()
    expected = models.PositiveIntegerField(default=0)
    completed = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ['-date', 'unit']


class Attachment(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='atendimentos/%Y/%m/')
    name = models.CharField(max_length=255)
