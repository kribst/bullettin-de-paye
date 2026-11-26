from rest_framework.permissions import BasePermission, SAFE_METHODS


def _company(user):
    return getattr(user, "company_id", None)


def _same_company(user, obj_company_id):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_super_admin", False) or user.is_superuser:
        return True
    return _company(user) is not None and _company(user) == obj_company_id


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and (request.user.is_super_admin or request.user.is_superuser)
        )


class IsCompanyAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_company_admin)


class IsHRManager(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_hr_manager)


class IsPayrollManager(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_payroll_manager)


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_manager)


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_employee_role)


class IsAuditor(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_auditor)


class CanManageHR(BasePermission):
    """Write access: super/tenant admins and HR managers. All mutations are tenant filtered."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if user.is_super_admin or user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            return bool(
                user.is_company_admin
                or user.is_hr_manager
                or user.is_payroll_manager
                or user.is_manager
                or user.is_auditor
                or user.is_employee_role
                or getattr(user, "role", None) == "hr"
            )
        return bool(
            user.is_company_admin
            or user.is_hr_manager
            or getattr(user, "role", None) == "hr"
            or getattr(user, "is_hr", False)
        )


class CanManagePayroll(BasePermission):
    """Payroll access is restricted to payroll, HR and tenant/platform administrators."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if user.is_super_admin or user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            return bool(user.is_company_admin or user.is_hr_manager or getattr(user, "role", None) == "hr"
                        or user.is_payroll_manager)
        return bool(user.is_company_admin or user.is_hr_manager or getattr(user, "role", None) == "hr"
                    or user.is_payroll_manager)


class CanManageCompany(BasePermission):
    """SUPER_ADMIN sur toute entreprise ; COMPANY_ADMIN uniquement sur la sienne (écriture)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_super_admin or request.user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            return request.user.is_company_admin
        return request.user.is_company_admin

    def has_object_permission(self, request, view, obj):
        company_id = getattr(obj, "company_id", None)
        if company_id is None and hasattr(obj, "id"):
            company_id = obj.id
        return _same_company(request.user, company_id)


class CanManageCompanyUsers(BasePermission):
    """SUPER_ADMIN gère tous les utilisateurs ; COMPANY_ADMIN uniquement les siens, rôles ordinaires seulement."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_super_admin or request.user.is_superuser or request.user.is_company_admin

    def has_object_permission(self, request, view, obj):
        if request.user.is_super_admin or request.user.is_superuser:
            return True
        if request.user.is_company_admin:
            return obj.company_id == request.user.company_id and request.user.can_manage_user(obj)
        return False


class IsSameCompany(BasePermission):
    """L'objet consulté appartient à l'entreprise de l'utilisateur (SUPER_ADMIN passe outre)."""

    def has_object_permission(self, request, view, obj):
        company_id = getattr(obj, "company_id", None)
        if company_id is None:
            company_id = getattr(obj, "id", None)
        return _same_company(request.user, company_id)
