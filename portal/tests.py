from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Attendance, Attachment


class PortalTests(TestCase):
    def test_unit_and_navigation(self):
        response = self.client.get('/?unit=imperatriz')
        self.assertContains(response, 'Unidade de Imperatriz')
        self.assertContains(response, 'Registrar atendimentos', count=1)
        self.assertNotContains(response, 'Um espaço para descobrir')
        self.assertNotContains(response, 'Selecionar unidade')
        self.assertContains(response, 'img/sesi.svg')

    def test_multiple_attachments_and_links(self):
        with TemporaryDirectory(dir='.') as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post('/atendimentos/novo/', {'unit': 'imperatriz', 'date': '2026-08-18', 'expected': 5, 'completed': 4, 'media': [SimpleUploadedFile('documento.pdf', b'%PDF-1.4\nexample', content_type='application/pdf'), SimpleUploadedFile('foto.png', b'\x89PNG\r\n\x1a\nexample', content_type='image/png')]})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Attachment.objects.count(), 2)
            self.assertTrue(all(item.file.storage.exists(item.file.name) for item in Attachment.objects.all()))
            response = self.client.get('/registros/?month=2026-08')
            self.assertContains(response, 'documento.pdf')
            self.assertContains(response, 'foto.png')

    def test_invalid_attachment_prevents_save(self):
        response = self.client.post('/atendimentos/novo/', {'unit': 'imperatriz', 'date': '2026-08-18', 'expected': 5, 'completed': 4, 'media': SimpleUploadedFile('fake.pdf', b'invalid')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)
