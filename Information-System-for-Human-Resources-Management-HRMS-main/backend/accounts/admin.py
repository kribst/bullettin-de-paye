from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Company, CompanyLeader, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "acronym", "legal_form", "is_active", "city", "country", "created_at")
    list_filter = ("is_active", "legal_form", "country", "created_at")
    search_fields = ("legal_name", "acronym", "tax_identification_number", "city")
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request):
        return bool(request.user.is_superuser or getattr(request.user, "is_super_admin", False))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(CompanyLeader)
class CompanyLeaderAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "position", "company", "created_at")
    list_filter = ("company", "created_at")
    search_fields = ("first_name", "last_name", "position", "company__legal_name")

    def has_module_permission(self, request):
        return bool(request.user.is_superuser or getattr(request.user, "is_super_admin", False))


@admin.register(User)
class HRUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "company", "employee", "is_active")
    list_filter = ("role", "company", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (("HRMS", {"fields": ("role", "company", "employee", "must_change_password")}),)

    def has_module_permission(self, request):
        return bool(request.user.is_superuser or getattr(request.user, "is_super_admin", False))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def save_model(self, request, obj, form, change):
        if obj.role == User.Role.SUPER_ADMIN:
            obj.is_superuser = True
            obj.is_staff = True
            obj.company = None
        elif obj.role in (User.Role.COMPANY_ADMIN,):
            if obj.company_id is None:
                raise ValueError("Un administrateur d'entreprise doit être rattaché à une entreprise.")
        super().save_model(request, obj, form, change)
