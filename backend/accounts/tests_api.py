from unittest import mock

from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .roles import ADMIN_GROUP, USER_GROUP

PASSWORD = "Clave-segura-2026"


def make_user(username, role="user", **extra):
    user = User.objects.create_user(username, password=PASSWORD, **extra)
    user.groups.add(Group.objects.get(name=ADMIN_GROUP if role == "admin" else USER_GROUP))
    return user


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("piloto")
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self):
        self.assertEqual(self.client.get("/api/auth/csrf/").status_code, 204)
        return self.client.cookies["csrftoken"].value

    def login(self, username="piloto", password=PASSWORD):
        return self.client.post("/api/auth/login/", {"username": username, "password": password},
                                format="json", HTTP_X_CSRFTOKEN=self.csrf())

    def test_anonymous_gets_401(self):
        for url in ("/api/auth/me/", "/api/users/", "/api/config/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    def test_login_requires_csrf(self):
        response = self.client.post("/api/auth/login/", {"username": "piloto", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_login_me_logout(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "user")
        self.assertFalse(response.json()["is_admin"])

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.json()["username"], "piloto")

        # Tras el login Django rota el token CSRF: se usa el nuevo.
        token = self.client.cookies["csrftoken"].value
        self.assertEqual(self.client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_wrong_password_and_inactive(self):
        self.assertEqual(self.login(password="mala").status_code, 400)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.login().status_code, 400)

    def test_login_is_throttled_per_username(self):
        for _ in range(10):
            self.login(password="mala")
        self.assertEqual(self.login().status_code, 429)


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = make_user("jefe", role="admin")
        self.user = make_user("piloto")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_registered_user_cannot_manage_users(self):
        client = APIClient()
        client.force_authenticate(self.user)
        self.assertEqual(client.get("/api/users/").status_code, 403)
        self.assertEqual(client.post("/api/users/", {"username": "x", "password": PASSWORD}).status_code, 403)
        self.assertEqual(client.patch(f"/api/users/{self.user.pk}/", {"role": "admin"}).status_code, 403)

    def test_list_does_not_expose_passwords(self):
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({u["username"]: u["role"] for u in response.json()}, {"jefe": "admin", "piloto": "user"})
        self.assertNotIn("password", str(response.json()))

    def test_create_user_and_admin(self):
        response = self.client.post("/api/users/", {"username": "nuevo", "password": PASSWORD, "first_name": "Ana"},
                                    format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["role"], "user")
        self.assertTrue(User.objects.get(username="nuevo").check_password(PASSWORD))

        response = self.client.post("/api/users/", {"username": "otro", "password": PASSWORD, "role": "admin"},
                                    format="json")
        self.assertEqual(response.json()["role"], "admin")

    def test_create_validates_password(self):
        response = self.client.post("/api/users/", {"username": "nuevo"}, format="json")
        self.assertIn("password", response.json())
        response = self.client.post("/api/users/", {"username": "nuevo", "password": "123"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_edit_role_and_password(self):
        response = self.client.patch(f"/api/users/{self.user.pk}/", {"role": "admin", "last_name": "Pérez"},
                                     format="json")
        self.assertEqual(response.json()["role"], "admin")
        self.assertEqual(list(self.user.groups.values_list("name", flat=True)), [ADMIN_GROUP])

        with mock.patch("accounts.views.disconnect_user_sync") as disconnect:
            self.client.patch(f"/api/users/{self.user.pk}/", {"password": "Otra-clave-2026"}, format="json")
        disconnect.assert_called_once_with(self.user.pk)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Otra-clave-2026"))

    def test_deactivate_ends_sessions_and_websockets(self):
        other = APIClient()
        other.login(username="piloto", password=PASSWORD)
        self.assertEqual(Session.objects.count(), 1)
        with mock.patch("accounts.views.disconnect_user_sync") as disconnect:
            response = self.client.patch(f"/api/users/{self.user.pk}/", {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        disconnect.assert_called_once_with(self.user.pk)
        self.assertEqual(Session.objects.count(), 0)
        self.assertEqual(other.get("/api/auth/me/").status_code, 401)

    def test_no_delete(self):
        self.assertEqual(self.client.delete(f"/api/users/{self.user.pk}/").status_code, 405)

    def test_admin_cannot_lock_themselves_out(self):
        url = f"/api/users/{self.admin.pk}/"
        self.assertIn("is_active", self.client.patch(url, {"is_active": False}, format="json").json())
        self.assertIn("role", self.client.patch(url, {"role": "user"}, format="json").json())

    def test_superuser_keeps_admin_role(self):
        root = User.objects.create_superuser("root", password=PASSWORD)
        response = self.client.patch(f"/api/users/{root.pk}/", {"role": "user"}, format="json")
        self.assertEqual(response.status_code, 400)
        client = APIClient()
        client.force_authenticate(root)
        self.assertEqual(client.get("/api/users/").status_code, 200)
