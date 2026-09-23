from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer para visualización y actualización del perfil del usuario."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "daily_hour_limit",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para registro de nuevos usuarios."""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "daily_hour_limit",
        ]
        extra_kwargs = {
            "daily_hour_limit": {"required": False},
        }

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Las contraseñas no coinciden."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer personalizado para JWT que agrega datos del usuario en la respuesta."""

    def validate(self, attrs):

         # ============================================================
        # 1. OBTENER LO QUE ESCRIBIÓ EL USUARIO
        # ============================================================
        #
        # El frontend siempre envía este campo como "username".
        #
        identifier = attrs.get("username")
        # ============================================================
        # 2. BUSCAR PRIMERO POR USERNAME
        # ============================================================
        # Intentamos encontrar un usuario cuyo username
        # coincida con lo que escribió el usuario.
    
        user = User.objects.filter(
            username=identifier
        ).first()

        # 3. SI NO EXISTE, BUSCAR POR EMAIL
        # ============================================================
        # Si no encontramos un username, intentamos buscar
        # por correo electrónico.
        if user is None:
            user = User.objects.filter(
                email__iexact=identifier
            ).first()

        # 4. CONVERTIR EMAIL → USERNAME
        # ============================================================
        #
        # SimpleJWT espera que "username" contenga el username.
        #
        # Si el usuario inició sesión utilizando su correo,
        # reemplazamos temporalmente:
        #
        # 
        # De esta manera podemos seguir utilizando
        # el sistema estándar de autenticación de Django.
        # ============================================================
        # 5. AUTENTICACIÓN NORMAL DE SIMPLEJWT
        # ============================================================
        if user is not None:
            attrs["username"] = user.username


        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "daily_hour_limit": str(self.user.daily_hour_limit),
        }
        return data
