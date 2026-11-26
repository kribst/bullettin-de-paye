import logging
import secrets

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Company, CompanyLeader, User
from .permissions import CanManageCompany, CanManageCompanyUsers
from .serializers import CompanyLeaderSerializer, CompanySerializer, UserCreateSerializer, UserSerializer

logger = logging.getLogger("hrms.accounts")


def user_payload(user):
    emp = user.employee
    role = user.role
    # L'ancien rôle "hr" reste accepté par les anciens clients.
    if role == User.Role.HR_MANAGER:
        role = "hr"
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": role,
        "role_code": user.role,
        "company_id": user.company_id,
        "company": user.company.legal_name if user.company else None,
        "must_change_password": user.must_change_password,
        "employee": None
        if emp is None
        else {
            "id": emp.id,
            "first_name": emp.first_name,
            "last_name": emp.last_name,
            "position": emp.position,
            "service": emp.service.name if emp.service_id else None,
        },
    }


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    """Sets the csrftoken cookie; the frontend sends the token back in the X-CSRFToken header."""
    return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        user = authenticate(request, username=email, password=password)
        if user is None:
            existing = User.objects.filter(username=email).first()
            if existing is not None and not existing.is_active:
                return Response({"detail": "Ce compte est désactivé.", "code": "account_disabled"},
                                status=status.HTTP_400_BAD_REQUEST)
            if existing is not None and existing.company_id is not None and not existing.company.is_active:
                return Response({"detail": "L'entreprise de ce compte est désactivée.", "code": "company_disabled"},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "Invalid email or password.", "code": "invalid_credentials"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({"detail": "Ce compte est désactivé.", "code": "account_disabled"},
                            status=status.HTTP_400_BAD_REQUEST)
        if user.company_id is not None and not user.company.is_active:
            return Response({"detail": "L'entreprise de ce compte est désactivée.", "code": "company_disabled"},
                            status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response({**user_payload(user), "csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response({"ok": True, "csrfToken": get_token(request)})


@api_view(["GET"])
@permission_classes([AllowAny])
def me(request):
    """The logged-in user, or null for a visitor."""
    from django.http import JsonResponse
    if not request.user.is_authenticated:
        return JsonResponse(None, safe=False)
    return Response(user_payload(request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    if not user.check_password(str(request.data.get("old_password", ""))):
        return Response({"detail": "Wrong password.", "code": "wrong_password", "field": "old_password"},
                        status=status.HTTP_400_BAD_REQUEST)
    new = str(request.data.get("new_password", ""))
    try:
        validate_password(new, user)
    except ValidationError as e:
        return Response({"new_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
    user.set_password(new)
    user.must_change_password = False
    user.save()
    update_session_auth_hash(request, user)
    return Response({"ok": True, "csrfToken": get_token(request)})


# --------------------------------------------------------------------------- entreprises

class CompanyListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_super_admin or user.is_superuser:
            qs = Company.objects.all()
        elif user.is_company_admin:
            qs = Company.objects.filter(pk=user.company_id)
        else:
            return Response({"detail": "Non autorisé.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        return Response(CompanySerializer(qs, many=True, context={"request": request}).data)

    def post(self, request):
        user = request.user
        if not (user.is_super_admin or user.is_superuser):
            return Response({"detail": "Seul un superadministrateur peut créer une entreprise.", "code": "forbidden"},
                            status=status.HTTP_403_FORBIDDEN)
        ser = CompanySerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        company = ser.save()
        logger.info("Company created: %s (by %s)", company.legal_name, user.email)
        return Response(CompanySerializer(company, context={"request": request}).data, status=status.HTTP_201_CREATED)


class CompanyMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_super_admin or user.is_superuser:
            return Response({"detail": "Le superadministrateur n'a pas d'entreprise propre.", "code": "no_company"},
                            status=status.HTTP_404_NOT_FOUND)
        if not user.company_id:
            return Response({"detail": "Aucune entreprise rattachée.", "code": "no_company"}, status=status.HTTP_404_NOT_FOUND)
        company = get_object_or_404(Company, pk=user.company_id)
        return Response(CompanySerializer(company, context={"request": request}).data)


class CompanyDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageCompany]

    def _check(self, request, company):
        user = request.user
        if not (user.is_super_admin or user.is_superuser) and (
            not user.is_company_admin or user.company_id != company.pk
        ):
            self.permission_denied(request)

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        self._check(request, company)
        return Response(CompanySerializer(company, context={"request": request}).data)

    def put(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        self._check(request, company)
        user = request.user
        data = request.data
        if not (user.is_super_admin or user.is_superuser):
            data = {k: v for k, v in data.items() if k != "is_active"}
        ser = CompanySerializer(company, data=data, partial=False, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        logger.info("Company updated: %s (by %s)", company.legal_name, user.email)
        return Response(CompanySerializer(company, context={"request": request}).data)

    def patch(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        self._check(request, company)
        user = request.user
        data = request.data
        if not (user.is_super_admin or user.is_superuser):
            data = {k: v for k, v in data.items() if k != "is_active"}
        ser = CompanySerializer(company, data=data, partial=True, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        logger.info("Company patched: %s (by %s)", company.legal_name, user.email)
        return Response(CompanySerializer(company, context={"request": request}).data)


class CompanyLogoView(APIView):
    permission_classes = [IsAuthenticated, CanManageCompany]
    parser_classes = [MultiPartParser, FormParser]

    def _check(self, request, company):
        user = request.user
        if not (user.is_super_admin or user.is_superuser) and (
            not user.is_company_admin or user.company_id != company.pk
        ):
            self.permission_denied(request)

    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        self._check(request, company)
        file = request.FILES.get("logo")
        if not file:
            return Response({"logo": "Aucun fichier fourni."}, status=status.HTTP_400_BAD_REQUEST)
        company.logo = file
        company.save()
        logger.info("Company logo updated: %s (by %s)", company.legal_name, request.user.email)
        return Response(CompanySerializer(company, context={"request": request}).data)


class CompanyLeaderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request, company_pk):
        company = get_object_or_404(Company, pk=company_pk)
        user = request.user
        if not (user.is_super_admin or user.is_superuser) and (
            not user.is_company_admin or user.company_id != company.pk
        ):
            self.permission_denied(request)
        return company

    def get(self, request, company_pk):
        company = self._company(request, company_pk)
        qs = CompanyLeader.objects.filter(company=company)
        return Response(CompanyLeaderSerializer(qs, many=True).data)

    def post(self, request, company_pk):
        company = self._company(request, company_pk)
        ser = CompanyLeaderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(company=company)
        logger.info("Company leader added for %s (by %s)", company.legal_name, request.user.email)
        return Response(ser.data, status=status.HTTP_201_CREATED)


class CompanyLeaderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request, company_pk):
        company = get_object_or_404(Company, pk=company_pk)
        user = request.user
        if not (user.is_super_admin or user.is_superuser) and (
            not user.is_company_admin or user.company_id != company.pk
        ):
            self.permission_denied(request)
        return company

    def _leader(self, request, company_pk, pk):
        company = self._company(request, company_pk)
        return get_object_or_404(CompanyLeader, pk=pk, company=company)

    def patch(self, request, company_pk, pk):
        leader = self._leader(request, company_pk, pk)
        ser = CompanyLeaderSerializer(leader, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, company_pk, pk):
        leader = self._leader(request, company_pk, pk)
        leader.delete()
        logger.info("Company leader deleted: %s (by %s)", pk, request.user.email)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- utilisateurs

def _user_queryset(request):
    user = request.user
    if user.is_super_admin or user.is_superuser:
        return User.objects.all()
    if user.is_company_admin:
        return User.objects.filter(company_id=user.company_id)
    return User.objects.filter(pk=user.pk)


class UserListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanManageCompanyUsers]

    def get(self, request):
        qs = _user_queryset(request).select_related("company", "employee")
        return Response(UserSerializer(qs, many=True).data)

    def post(self, request):
        user = request.user
        if not (user.is_super_admin or user.is_superuser or user.is_company_admin):
            return Response({"detail": "Non autorisé à créer des comptes.", "code": "forbidden"},
                            status=status.HTTP_403_FORBIDDEN)
        ser = UserCreateSerializer(data=request.data, context={"request": request, "creator": user})
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            new_user = ser.save()
        logger.info("User created: %s (%s) company=%s (by %s)", new_user.email, new_user.role,
                    new_user.company_id, user.email)
        return Response(UserSerializer(new_user).data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageCompanyUsers]

    def _get(self, request, pk):
        user = request.user
        obj = get_object_or_404(User.objects.select_related("company", "employee"), pk=pk)
        if not (user.is_super_admin or user.is_superuser):
            if not user.is_company_admin or obj.company_id != user.company_id:
                self.permission_denied(request)
            if not user.can_manage_user(obj):
                self.permission_denied(request)
        return obj

    def get(self, request, pk):
        obj = self._get(request, pk)
        return Response(UserSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get(request, pk)
        requester = request.user
        data = dict(request.data)
        if not (requester.is_super_admin or requester.is_superuser):
            data.pop("company", None)
            data.pop("company_id", None)
        ser = UserSerializer(obj, data=data, partial=True, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        logger.info("User updated: %s (by %s)", obj.email, requester.email)
        return Response(UserSerializer(obj).data)


class UserDeactivateView(APIView):
    permission_classes = [IsAuthenticated, CanManageCompanyUsers]

    def post(self, request, pk):
        requester = request.user
        obj = get_object_or_404(User, pk=pk)
        if requester.is_super_admin or requester.is_superuser:
            pass
        elif requester.is_company_admin:
            if obj.company_id != requester.company_id:
                return Response({"detail": "Non autorisé.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
            if obj.pk != requester.pk and obj.role in (User.Role.SUPER_ADMIN, User.Role.COMPANY_ADMIN):
                return Response({"detail": "Rôle non gérable.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
            if obj.pk == requester.pk:
                admins = User.objects.filter(company_id=requester.company_id, role=User.Role.COMPANY_ADMIN,
                                             is_active=True).exclude(pk=requester.pk)
                if not admins.exists():
                    return Response(
                        {"detail": "Impossible de se désactiver : vous êtes le dernier administrateur de l'entreprise.",
                         "code": "last_admin"},
                        status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": "Non autorisé.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        obj.is_active = False
        obj.save()
        logger.info("User deactivated: %s (by %s)", obj.email, requester.email)
        return Response({"detail": "Compte désactivé.", "code": "deactivated"})


class UserActivateView(APIView):
    permission_classes = [IsAuthenticated, CanManageCompanyUsers]

    def post(self, request, pk):
        requester = request.user
        obj = get_object_or_404(User, pk=pk)
        if not (requester.is_super_admin or requester.is_superuser):
            if not requester.is_company_admin or obj.company_id != requester.company_id:
                return Response({"detail": "Non autorisé.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
            if not requester.can_manage_user(obj):
                return Response({"detail": "Rôle non gérable.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        obj.is_active = True
        obj.save()
        logger.info("User activated: %s (by %s)", obj.email, requester.email)
        return Response({"detail": "Compte activé.", "code": "activated"})


class UserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, CanManageCompanyUsers]

    def post(self, request, pk):
        requester = request.user
        obj = get_object_or_404(User, pk=pk)
        if not (requester.is_super_admin or requester.is_superuser):
            if not requester.is_company_admin or obj.company_id != requester.company_id:
                return Response({"detail": "Non autorisé.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
            if not requester.can_manage_user(obj):
                return Response({"detail": "Rôle non gérable.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        password = secrets.token_urlsafe(12)
        obj.set_password(password)
        obj.must_change_password = True
        obj.save()
        logger.info("Password reset for: %s (by %s)", obj.email, requester.email)
        return Response({"temporary_password": password, "must_change_password": True})
