from datetime import date
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.test import LiveServerTestCase
from .models import PerfilUsuario, Polo, Atendimento, Evento, Indicador, MetaMensal, AnexoAtendimento


class AccessTests(TestCase):
    def setUp(self):
        self.a = Polo.objects.create(nome='Polo Alfa')
        self.b = Polo.objects.create(nome='Polo Beta')
        self.admin = get_user_model().objects.create_user('admin-negocio', password='test-password')
        PerfilUsuario.objects.create(user=self.admin, tipo='ADMIN')
        self.manager = get_user_model().objects.create_user('gerente', password='test-password', is_staff=True)
        PerfilUsuario.objects.create(user=self.manager, tipo='GERENTE', polo=self.a)
        self.aa = Atendimento.objects.create(polo=self.a, data=date(2026, 10, 15), observacao='nota alfa')
        self.ab = Atendimento.objects.create(polo=self.b, data=date(2026, 10, 15), observacao='nota beta')

    def data(self, **kwargs):
        return {'polo': self.b.pk, 'data': '2026-10-15', 'livros_retirados': 3, **kwargs}

    def test_anonymous_routes_redirect(self):
        for url in ['/', '/registros/', '/atendimentos/novo/', f'/atendimentos/{self.aa.pk}/editar/', f'/atendimentos/{self.aa.pk}/excluir/', '/media/secret.jpg']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('/login/?next='))

    def test_login_logout_and_invalid_password(self):
        self.client.post('/login/', {'username': 'gerente', 'password': 'wrong'})
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertRedirects(self.client.post('/login/', {'username': 'gerente', 'password': 'test-password'}), '/')
        self.assertEqual(self.client.get('/').context['polo'], self.a)
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        self.assertRedirects(self.client.post('/logout/'), '/login/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_rejects_external_redirect(self):
        response = self.client.post('/login/', {'username': 'gerente', 'password': 'test-password', 'next': 'https://evil.example/'})
        self.assertEqual(response.url, '/')

    def test_admin_home_and_records_all_polos(self):
        self.client.force_login(self.admin)
        for polo in [self.a, self.b]:
            self.assertEqual(self.client.get('/', {'unit': polo.pk}).context['polo'], polo)
        response = self.client.get('/registros/?month=2026-10')
        for text in ['Polo Alfa', 'Polo Beta', 'nota alfa', 'nota beta']:
            self.assertContains(response, text)
        filtered = self.client.get('/registros/', {'polo': self.b.pk})
        self.assertEqual([r['name'] for r in filtered.context['rows']], [self.b.nome])

    def test_admin_creates_edits_deletes_any_polo(self):
        self.client.force_login(self.admin)
        for polo in [self.a, self.b]:
            self.assertEqual(self.client.post('/atendimentos/novo/', self.data(polo=polo.pk)).status_code, 302)
        for entry in [self.aa, self.ab]:
            url = f'/atendimentos/{entry.pk}/editar/'
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.post(url, self.data(observacao='alterada')).status_code, 302)
            entry.refresh_from_db()
            self.assertEqual(entry.observacao, 'alterada')
            url = f'/atendimentos/{entry.pk}/excluir/'
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertTrue(Atendimento.objects.filter(pk=entry.pk).exists())
            self.assertEqual(self.client.post(url).status_code, 302)
            self.assertFalse(Atendimento.objects.filter(pk=entry.pk).exists())

    def test_manager_query_manipulation_and_reports(self):
        self.client.force_login(self.manager)
        for key in ['unit', 'polo', 'polo_id']:
            response = self.client.get('/', {key: self.b.pk, 'month': '2026-10'})
            self.assertEqual(response.context['polo'], self.a)
            self.assertNotContains(response, self.b.nome)
            response = self.client.get('/registros/', {key: self.b.pk, 'month': '2026-10'})
            self.assertContains(response, 'nota alfa')
            self.assertNotContains(response, 'nota beta')
            self.assertNotContains(response, 'Excluir')

    def test_manager_edit_own_and_cannot_move_polo(self):
        self.client.force_login(self.manager)
        url = f'/atendimentos/{self.aa.pk}/editar/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, self.data(polo_id=self.b.pk, observacao='permitida')).status_code, 302)
        self.aa.refresh_from_db()
        self.assertEqual(self.aa.polo, self.a)
        self.assertEqual(self.aa.observacao, 'permitida')

    def test_manager_attack_other_record_get_post_delete(self):
        self.client.force_login(self.manager)
        url = f'/atendimentos/{self.ab.pk}/editar/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.data()).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.ab.refresh_from_db()
        self.assertEqual(self.ab.observacao, 'nota beta')
        for entry in [self.aa, self.ab]:
            url = f'/atendimentos/{entry.pk}/excluir/'
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url).status_code, 403)
            self.assertEqual(self.client.delete(url).status_code, 405)
            self.assertTrue(Atendimento.objects.filter(pk=entry.pk).exists())

    def test_manager_create_ignores_forged_polo(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post('/atendimentos/novo/', self.data()).status_code, 302)
        self.assertEqual(Atendimento.objects.latest('pk').polo, self.a)

    def test_events_and_metas_scoped(self):
        indicador = Indicador.objects.create(codigo='qtd', nome='Atendimentos', tipo_calculo='quantidade_atendimentos')
        for polo, value in [(self.a, 111), (self.b, 999)]:
            Evento.objects.create(polo=polo, titulo=polo.nome + ' evento', data_inicio=date(2026, 10, 1), data_fim=date(2026, 10, 31))
            MetaMensal.objects.create(polo=polo, indicador=indicador, competencia=date(2026, 10, 1), previsto=value)
        self.client.force_login(self.manager)
        response = self.client.get('/?month=2026-10')
        self.assertEqual([e.polo_id for e in response.context['eventos']], [self.a.pk])
        self.assertEqual(response.context['metas'][0]['mensal'], 111)
        self.assertNotContains(response, 'Polo Beta evento')
        response = self.client.get('/registros/?month=2026-10')
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(response.context['rows'][0]['metas'][0]['mensal'], 111)
        foreign = Evento.objects.get(polo=self.b)
        self.assertEqual(self.client.post('/atendimentos/novo/', self.data(evento=foreign.pk)).status_code, 200)

    def test_profile_validation_and_database_constraint(self):
        from django.db import IntegrityError, transaction
        user = get_user_model().objects.create_user('invalid')
        for tipo, polo in [('GERENTE', None), ('ADMIN', self.a), ('BAD', None)]:
            perfil = PerfilUsuario(user=user, tipo=tipo, polo=polo)
            with self.assertRaises(ValidationError):
                perfil.full_clean()
            with self.assertRaises(IntegrityError), transaction.atomic():
                perfil.save()

    def test_user_without_profile_denied(self):
        self.client.force_login(get_user_model().objects.create_user('no-profile'))
        for url in ['/', '/registros/', '/atendimentos/novo/']:
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_superuser_and_technical_admin(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/admin/').status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin/').status_code, 403)
        superuser = get_user_model().objects.create_superuser('technical', password='test-password')
        self.client.force_login(superuser)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_csrf_enforced_on_login_edit_delete_logout(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/login/', {}).status_code, 403)
        client.force_login(self.admin)
        for url in ['/logout/', f'/atendimentos/{self.aa.pk}/editar/', f'/atendimentos/{self.aa.pk}/excluir/']:
            self.assertEqual(client.post(url, self.data()).status_code, 403)

    def test_media_cannot_bypass_scope(self):
        with TemporaryDirectory(dir='.') as directory, override_settings(MEDIA_ROOT=directory):
            anexo = AnexoAtendimento.objects.create(atendimento=self.ab, arquivo=SimpleUploadedFile('secret.jpg', b'abc'), nome_original='secret.jpg')
            self.client.force_login(self.manager)
            self.assertEqual(self.client.get(anexo.arquivo.url).status_code, 404)
            self.client.force_login(self.admin)
            response = self.client.get(anexo.arquivo.url)
            self.assertEqual(response.status_code, 200)
            response.close()


class AccessHTTPTests(LiveServerTestCase):
    def test_real_http_admin_manager_edit_delete_logout(self):
        import re
        from urllib.request import build_opener, HTTPCookieProcessor
        from urllib.error import HTTPError
        from urllib.parse import urlencode
        from http.cookiejar import CookieJar

        a = Polo.objects.create(nome='HTTP Alfa')
        b = Polo.objects.create(nome='HTTP Beta')
        own = Atendimento.objects.create(polo=a, data=date(2026, 10, 15))
        other = Atendimento.objects.create(polo=b, data=date(2026, 10, 15))

        def request(browser, path, data=None):
            try:
                with browser.open(self.live_server_url + path, data=urlencode(data).encode() if data is not None else None, timeout=10) as response:
                    return response.status, response.read().decode(), response.url
            except HTTPError as error:
                error.close()
                return error.code, '', ''

        def token(html):
            return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)

        for role in ['GERENTE', 'ADMIN']:
            user = get_user_model().objects.create_user(role, password='http-password')
            PerfilUsuario.objects.create(user=user, tipo=role, polo=a if role == 'GERENTE' else None)
            browser = build_opener(HTTPCookieProcessor(CookieJar()))
            status, html, _ = request(browser, '/login/')
            self.assertEqual(status, 200)
            status, html, url = request(browser, '/login/', {'username': role, 'password': 'http-password', 'csrfmiddlewaretoken': token(html)})
            self.assertEqual(status, 200)
            self.assertTrue(url.endswith('/'))
            self.assertIn(a.nome, html)
            if role == 'GERENTE':
                self.assertNotIn(b.nome, html)
            status, html, _ = request(browser, '/registros/?month=2026-10')
            self.assertEqual(status, 200)
            self.assertEqual(b.nome in html, role == 'ADMIN')
            path = f'/atendimentos/{own.pk}/editar/'
            status, html, _ = request(browser, path)
            self.assertEqual(status, 200)
            status, _, _ = request(browser, path, {'csrfmiddlewaretoken': token(html), 'polo': a.pk, 'data': '2026-10-15', 'livros_retirados': 7})
            self.assertEqual(status, 200)
            other_edit = f'/atendimentos/{other.pk}/editar/'
            self.assertEqual(request(browser, other_edit)[0], 404 if role == 'GERENTE' else 200)
            deletion = f'/atendimentos/{other.pk}/excluir/'
            status, html, _ = request(browser, deletion)
            self.assertEqual(status, 403 if role == 'GERENTE' else 200)
            if role == 'ADMIN':
                self.assertEqual(request(browser, deletion, {'csrfmiddlewaretoken': token(html)})[0], 200)
                self.assertFalse(Atendimento.objects.filter(pk=other.pk).exists())
            _, html, _ = request(browser, '/')
            status, _, url = request(browser, '/logout/', {'csrfmiddlewaretoken': token(html)})
            self.assertEqual(status, 200)
            self.assertTrue(url.endswith('/login/'))
            self.assertIn('/login/', request(browser, '/')[2])
