from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Company = apps.get_model("accounts", "Company")
    Employee = apps.get_model("hr", "Employee")
    Service = apps.get_model("hr", "Service")

    company, _ = Company.objects.get_or_create(
        legal_name="Entreprise par défaut",
        defaults={"acronym": "DEF", "legal_form": "autre", "is_active": True},
    )
    User.objects.filter(company__isnull=True).exclude(is_superuser=True).update(company=company)
    for employee in Employee.objects.filter(company__isnull=True):
        try:
            company_id = employee.user.company_id
        except User.DoesNotExist:
            company_id = company.id
        employee.company_id = company_id or company.id
        employee.save(update_fields=["company"])
    Service.objects.filter(company__isnull=True).update(company=company)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_company_alter_user_role_user_company_companyleader"),
        ("hr", "0002_employee_company_service_company"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
