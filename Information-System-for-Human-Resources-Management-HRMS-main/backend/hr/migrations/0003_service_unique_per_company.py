from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hr", "0002_employee_company_service_company"),
    ]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AddConstraint(
            model_name="service",
            constraint=models.UniqueConstraint(
                fields=("company", "name"),
                name="unique_service_name_per_company",
            ),
        ),
    ]
