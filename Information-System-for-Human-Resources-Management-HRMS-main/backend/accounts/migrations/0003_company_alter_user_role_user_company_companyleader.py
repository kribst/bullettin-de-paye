# Generated during the HRMS multi-tenant implementation.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legal_name", models.CharField(max_length=200, verbose_name="dénomination sociale")),
                ("acronym", models.CharField(blank=True, max_length=20, verbose_name="sigle")),
                ("legal_form", models.CharField(choices=[("SARL", "SARL"), ("SA", "SA"), ("SAS", "SAS"), ("SNC", "SNC"), ("SCS", "SCS"), ("entreprise_individuelle", "Entreprise individuelle"), ("autre", "Autre")], default="autre", max_length=30, verbose_name="forme juridique")),
                ("legal_creation_date", models.DateField(blank=True, null=True, verbose_name="date de création juridique")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="enregistrée le")),
                ("activity_sector", models.CharField(blank=True, max_length=100, verbose_name="secteur d'activité")),
                ("official_description", models.TextField(blank=True, verbose_name="description officielle")),
                ("nationality", models.CharField(blank=True, max_length=100, verbose_name="nationalité")),
                ("tax_identification_number", models.CharField(blank=True, help_text="Format adapté au pays de l'entreprise.", max_length=50, validators=[django.core.validators.RegexValidator("^[A-Za-z0-9 \\-/.]+$", "Numéro d'identification invalide.")], verbose_name="NIU / numéro fiscal")),
                ("country", models.CharField(blank=True, max_length=100, verbose_name="pays")),
                ("city", models.CharField(blank=True, max_length=100, verbose_name="ville")),
                ("district", models.CharField(blank=True, max_length=100, verbose_name="quartier")),
                ("postal_box", models.CharField(blank=True, max_length=20, verbose_name="boîte postale")),
                ("website", models.URLField(blank=True, verbose_name="site Internet")),
                ("logo", models.ImageField(blank=True, null=True, upload_to="company_logos/", verbose_name="logo")),
                ("director_first_name", models.CharField(blank=True, max_length=100, verbose_name="prénom du dirigeant")),
                ("director_last_name", models.CharField(blank=True, max_length=100, verbose_name="nom du dirigeant")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="modifiée le")),
            ],
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(choices=[("super_admin", "Superadministrateur"), ("company_admin", "Administrateur d'entreprise"), ("hr_manager", "Responsable RH"), ("payroll_manager", "Responsable de la paie"), ("accountant", "Comptable"), ("manager", "Responsable de département"), ("employee", "Employé"), ("auditor", "Auditeur"), ("hr", "RH (ancien)")], default="employee", max_length=20),
        ),
        migrations.AddField(
            model_name="user",
            name="company",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="users", to="accounts.company", verbose_name="entreprise"),
        ),
        migrations.CreateModel(
            name="CompanyLeader",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_name", models.CharField(max_length=100, verbose_name="prénom")),
                ("last_name", models.CharField(max_length=100, verbose_name="nom")),
                ("position", models.CharField(blank=True, max_length=100, verbose_name="fonction")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="enregistré le")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leaders", to="accounts.company")),
            ],
        ),
    ]
