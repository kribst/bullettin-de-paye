from django.contrib import admin

from .models import Application, Attendance, Contract, Employee, JobOffer, Leave, Payslip, Service


class SuperAdminOnly:
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


@admin.register(Service)
class ServiceAdmin(SuperAdminOnly, admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Employee)
class EmployeeAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["last_name", "first_name", "email", "service", "position", "status", "hire_date"]
    list_filter = ["service", "status"]
    search_fields = ["first_name", "last_name", "email"]


@admin.register(Contract)
class ContractAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["employee", "type", "start_date", "end_date", "monthly_salary", "archived"]
    list_filter = ["type", "archived"]


@admin.register(Leave)
class LeaveAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["employee", "type", "start_date", "end_date", "days", "status"]
    list_filter = ["type", "status"]


@admin.register(Attendance)
class AttendanceAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["employee", "date", "status", "check_in", "check_out"]
    list_filter = ["status", "date"]


@admin.register(Payslip)
class PayslipAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["employee", "period", "gross", "net", "status"]
    list_filter = ["period", "status"]


@admin.register(JobOffer)
class JobOfferAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["title", "service", "contract_type", "deadline", "status"]


@admin.register(Application)
class ApplicationAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["last_name", "first_name", "offer", "status", "created_at"]
    list_filter = ["status", "offer"]
