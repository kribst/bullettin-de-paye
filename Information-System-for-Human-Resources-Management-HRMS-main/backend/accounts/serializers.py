from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers

from .models import Company, CompanyLeader, User

User = get_user_model()


class CompanyLeaderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyLeader
        fields = ["id", "company", "first_name", "last_name", "position", "created_at"]
        read_only_fields = ["id", "company", "created_at"]


class CompanySerializer(serializers.ModelSerializer):
    leaders = CompanyLeaderSerializer(many=True, read_only=True)
    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Company
        fields = [
            "id", "legal_name", "acronym", "legal_form", "legal_creation_date", "created_at",
            "activity_sector", "official_description", "nationality", "tax_identification_number",
            "country", "city", "district", "postal_box", "website", "logo", "logo_url",
            "director_first_name", "director_last_name", "is_active", "updated_at", "leaders",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "leaders", "logo_url"]

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

    def validate_tax_identification_number(self, value):
        if value:
            return value.strip().upper()
        return value

    def validate(self, data):
        # is_active ne peut être modifié que par un SUPER_ADMIN (vu côté vue).
        return data


class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source="company", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "role", "company", "company_id",
            "employee", "is_active", "is_staff", "is_superuser", "must_change_password", "date_joined",
        ]
        read_only_fields = ["id", "employee", "is_staff", "is_superuser", "date_joined"]

    def validate(self, data):
        request = self.context.get("request")
        requester = getattr(request, "user", None)
        if not requester:
            return data

        role = data.get("role", getattr(self.instance, "role", None))
        company = data.get("company", getattr(self.instance, "company", None))

        if self.instance and self.instance.pk == requester.pk:
            for field in ("role", "company", "company_id", "is_active"):
                if field in data:
                    raise serializers.ValidationError(
                        "Vous ne pouvez pas modifier votre propre rôle, votre entreprise ou votre activation."
                    )

        if not (requester.is_super_admin or requester.is_superuser):
            if requester.is_company_admin:
                if role in (User.Role.SUPER_ADMIN, User.Role.COMPANY_ADMIN):
                    raise serializers.ValidationError({"role": "Ce rôle ne peut pas être attribué par un administrateur d'entreprise."})
                if role not in requester.ordinary_roles:
                    raise serializers.ValidationError({"role": "Rôle non autorisé."})
                if company and company.pk != requester.company_id:
                    raise serializers.ValidationError({"company": "Rattachement à une autre entreprise interdit."})

        return data


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name", "role", "company", "must_change_password"]

    def __init__(self, *args, **kwargs):
        self.creator = None
        super().__init__(*args, **kwargs)
        if self.creator is None:
            self.creator = self.context.get("creator")

    def validate_password(self, value):
        try:
            validate_password(value, self.instance)
        except ValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, data):
        creator = self.creator
        role = data.get("role")
        company = data.get("company")

        if creator is None:
            raise serializers.ValidationError({"detail": "Créateur requis."})

        if creator.is_super_admin or creator.is_superuser:
            if role == User.Role.SUPER_ADMIN:
                raise serializers.ValidationError(
                    {"role": "Le rôle superadministrateur ne peut être attribué que par createsuperuser ou le mécanisme Django sécurisé."}
                )
            if role in (User.Role.COMPANY_ADMIN,) and not company:
                raise serializers.ValidationError({"company": "Un administrateur d'entreprise doit être rattaché."})
            if role in creator.ordinary_roles and not company:
                raise serializers.ValidationError({"company": "L'utilisateur doit être rattaché à une entreprise."})
            return data

        if creator.is_company_admin:
            # Seul le SUPER_ADMIN crée des entreprises et des COMPANY_ADMIN / SUPER_ADMIN.
            if role in (User.Role.SUPER_ADMIN, User.Role.COMPANY_ADMIN):
                raise serializers.ValidationError({"role": "Ce rôle ne peut pas être créé par un administrateur d'entreprise."})
            if role not in creator.ordinary_roles:
                raise serializers.ValidationError({"role": "Rôle non autorisé pour un administrateur d'entreprise."})
            # L'utilisateur est rattaché à l'entreprise du créateur, jamais à une entreprise choisie frontalement.
            data["company"] = creator.company
            if not data["company"]:
                raise serializers.ValidationError({"detail": "Votre compte n'est rattaché à aucune entreprise."})
            return data

        raise serializers.ValidationError({"detail": "Vous n'êtes pas autorisé à créer des comptes."})

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.setdefault("username", validated_data.get("email"))
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user
