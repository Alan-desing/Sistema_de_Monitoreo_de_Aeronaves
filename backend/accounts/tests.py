from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase

from .roles import ADMIN_GROUP, ROLE_ADMIN, ROLE_GROUPS, ROLE_USER, USER_GROUP, is_admin, role_of


class RoleTests(TestCase):
    def test_groups_created_by_migration(self):
        self.assertEqual(
            set(Group.objects.filter(name__in=ROLE_GROUPS).values_list("name", flat=True)),
            set(ROLE_GROUPS),
        )

    def test_admin_group_member_is_admin(self):
        user = User.objects.create_user("ana", password="x")
        user.groups.add(Group.objects.get(name=ADMIN_GROUP))
        self.assertTrue(is_admin(user))
        self.assertEqual(role_of(user), ROLE_ADMIN)

    def test_registered_user_is_not_admin(self):
        user = User.objects.create_user("beto", password="x")
        user.groups.add(Group.objects.get(name=USER_GROUP))
        self.assertFalse(is_admin(user))
        self.assertEqual(role_of(user), ROLE_USER)

    def test_superuser_is_admin_without_group(self):
        user = User.objects.create_superuser("root", password="x")
        self.assertTrue(is_admin(user))

    def test_inactive_or_anonymous_is_not_admin(self):
        user = User.objects.create_superuser("viejo", password="x", is_active=False)
        self.assertFalse(is_admin(user))
        self.assertFalse(is_admin(AnonymousUser()))
