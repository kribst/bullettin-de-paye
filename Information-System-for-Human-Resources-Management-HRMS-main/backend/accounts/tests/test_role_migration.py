from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RoleMergeMigrationTests(TransactionTestCase):
    migrate_from = ("accounts", "0005_alter_company_options_alter_companyleader_options_and_more")
    migrate_to = ("accounts", "0006_alter_user_role")

    def test_existing_accountant_is_migrated_to_payroll_manager(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        Company = old_apps.get_model("accounts", "Company")
        User = old_apps.get_model("accounts", "User")

        company = Company.objects.create(legal_name="Legacy account migration")
        user = User.objects.create(
            username="legacy.accountant@example.test",
            email="legacy.accountant@example.test",
            password="!",
            role="accountant",
            company=company,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        MigratedUser = new_apps.get_model("accounts", "User")

        self.assertEqual(
            MigratedUser.objects.get(pk=user.pk).role,
            "payroll_manager",
        )
