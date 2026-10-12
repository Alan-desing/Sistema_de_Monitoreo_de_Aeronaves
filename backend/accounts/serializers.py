from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .roles import ROLE_ADMIN, ROLE_CHOICES, ROLE_USER, role_of, set_role


class MeSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "role", "is_admin"]

    def get_role(self, user):
        return role_of(user)

    def get_is_admin(self, user):
        return role_of(user) == ROLE_ADMIN


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=ROLE_CHOICES, default=ROLE_USER)
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "role", "is_active", "is_superuser",
            "password", "last_login", "date_joined",
        ]
        read_only_fields = ["is_superuser", "last_login", "date_joined"]

    def to_representation(self, user):
        data = super().to_representation(user)
        data["role"] = role_of(user)
        return data

    def validate(self, attrs):
        user = self.instance
        if user is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "La contraseña es obligatoria."})

        if "password" in attrs:
            candidate = user or User(
                username=attrs.get("username", ""),
                first_name=attrs.get("first_name", ""),
                last_name=attrs.get("last_name", ""),
            )
            try:
                password_validation.validate_password(attrs["password"], candidate)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})

        if user is not None and user.is_superuser and attrs.get("role", ROLE_ADMIN) != ROLE_ADMIN:
            raise serializers.ValidationError(
                {"role": "Es superusuario: no se le puede quitar el rol de administrador desde la web."}
            )

        request = self.context.get("request")
        if user is not None and request is not None and user.pk == request.user.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "No podés desactivar tu propio usuario."})
            if attrs.get("role", ROLE_ADMIN) != ROLE_ADMIN:
                raise serializers.ValidationError({"role": "No podés quitarte el rol de administrador."})
        return attrs

    def create(self, validated_data):
        role = validated_data.pop("role", ROLE_USER)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        set_role(user, role)
        return user

    def update(self, user, validated_data):
        role = validated_data.pop("role", None)
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(user, field, value)
        if password:
            user.set_password(password)
        user.save()
        if role is not None:
            set_role(user, role)
        return user
