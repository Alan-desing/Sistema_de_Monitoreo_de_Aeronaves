"""Roles del sistema, implementados con grupos de Django.

Solo hay dos roles. Un superusuario (creado con ``createsuperuser``) se
considera administrador aunque no pertenezca al grupo.
"""

from django.contrib.auth.models import Group

ADMIN_GROUP = "Administrador"
USER_GROUP = "Usuario registrado"

ROLE_GROUPS = (ADMIN_GROUP, USER_GROUP)

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_CHOICES = ((ROLE_ADMIN, "Administrador"), (ROLE_USER, "Usuario registrado"))


def has_admin_role(user):
    """Rol asignado, sin mirar si la cuenta está activa."""
    return user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists()


def is_admin(user):
    """Si el usuario puede usar ahora las funciones de administrador."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return has_admin_role(user)


def role_of(user):
    return ROLE_ADMIN if has_admin_role(user) else ROLE_USER


def set_role(user, role):
    admin_group, user_group = (Group.objects.get_or_create(name=name)[0] for name in ROLE_GROUPS)
    user.groups.remove(admin_group, user_group)
    user.groups.add(admin_group if role == ROLE_ADMIN else user_group)
