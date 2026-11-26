from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Company, User
from hr.models import Employee, Service

User = get_user_model()

PASSWORD = "TestPass1234!"


def make_company(legal_name, acronym, is_active=True):
    return Company.objects.create(
        legal_name=legal_name, acronym=acronym, legal_form=Company.LegalForm.SARL,
        country="DZ", city="Alger", is_active=is_active,
    )


def make_user(email, role, company=None, password=PASSWORD, **extra):
    return User.objects.create_user(
        username=email, email=email, password=password, role=role, company=company, **extra
    )


class AuthClient(APIClient):
    """Client authentifié avec gestion du CSRF (session Django existante)."""

    def __init__(self, *args, **kwargs):
        super().__init__(enforce_csrf_checks=True, *args, **kwargs)
        self.token = None

    def login(self, email, password=PASSWORD):
        self.get("/api/auth/csrf/")
        self.token = self.cookies.get("csrftoken")
        if self.token:
            self.token = self.token.value
        r = self.post(
            "/api/auth/login/", {"email": email, "password": password},
            format="json", HTTP_X_CSRFTOKEN=self.token or "",
        )
        assert r.status_code == 200, r.content
        data = r.json()
        self.credentials(HTTP_X_CSRFTOKEN=data["csrfToken"])
        return data


class CompanyRoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comp_a = make_company("Entreprise A", "A")
        cls.comp_b = make_company("Entreprise B", "B")
        cls.super_admin = make_user("sa@plateforme.dz", User.Role.SUPER_ADMIN, company=None,
                                    is_superuser=True, is_staff=True)
        cls.admin_a = make_user("admin@a.dz", User.Role.COMPANY_ADMIN, cls.comp_a)
        cls.admin_b = make_user("admin@b.dz", User.Role.COMPANY_ADMIN, cls.comp_b)
        cls.emp_a = make_user("emp@a.dz", User.Role.EMPLOYEE, cls.comp_a)
        cls.payroll_manager_a = make_user("payroll@a.dz", User.Role.PAYROLL_MANAGER, cls.comp_a)
        cls.auditor_a = make_user("aud@a.dz", User.Role.AUDITOR, cls.comp_a)

    def setUp(self):
        cache.clear()

    # --- authentification existante préservée ---------------------------------

    def test_existing_auth_still_works(self):
        c = AuthClient()
        data = c.login("emp@a.dz")
        self.assertIn("csrfToken", data)
        r = c.get("/api/auth/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["email"], "emp@a.dz")
        r = c.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(r.status_code, 200)

    # --- entreprises ------------------------------------------------------------

    def test_superadmin_can_create_company(self):
        c = AuthClient()
        c.login("sa@plateforme.dz")
        r = c.post("/api/companies/", {"legal_name": "Entreprise C", "acronym": "C",
                                        "legal_form": "SARL", "country": "DZ"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Company.objects.filter(legal_name="Entreprise C").exists())

    def test_company_admin_cannot_create_company(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.post("/api/companies/", {"legal_name": "Entreprise C", "acronym": "C"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_company_admin_sees_only_own_company(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.get("/api/companies/")
        self.assertEqual(r.status_code, 200)
        ids = [x["id"] for x in r.json()]
        self.assertIn(self.comp_a.id, ids)
        self.assertNotIn(self.comp_b.id, ids)

    def test_company_admin_cannot_access_other_company(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.get(f"/api/companies/{self.comp_b.id}/")
        self.assertEqual(r.status_code, 403, r.content)
        r = c.patch(f"/api/companies/{self.comp_b.id}/", {"city": "Oran"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_superadmin_can_access_any_company(self):
        c = AuthClient()
        c.login("sa@plateforme.dz")
        r = c.get(f"/api/companies/{self.comp_b.id}/")
        self.assertEqual(r.status_code, 200, r.content)

    # --- utilisateurs -----------------------------------------------------------

    def test_superadmin_can_create_company_admin(self):
        c = AuthClient()
        c.login("sa@plateforme.dz")
        r = c.post("/api/accounts/users/", {"email": "ca@c.dz", "password": PASSWORD,
                                            "first_name": "Chef", "last_name": "EntrepriseC",
                                            "role": User.Role.COMPANY_ADMIN, "company": self.comp_c_id()}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        u = User.objects.get(email="ca@c.dz")
        self.assertEqual(u.role, User.Role.COMPANY_ADMIN)

    def test_superadmin_can_create_company_admin(self):
        company_c = Company.objects.create(legal_name="Entreprise C", acronym="C",
                                           legal_form=Company.LegalForm.SARL, country="DZ")
        c = AuthClient()
        c.login("sa@plateforme.dz")
        r = c.post("/api/accounts/users/", {"email": "ca@c.dz", "password": PASSWORD,
                                            "first_name": "Chef", "last_name": "EntrepriseC",
                                            "role": User.Role.COMPANY_ADMIN, "company": company_c.id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        u = User.objects.get(email="ca@c.dz")
        self.assertEqual(u.role, User.Role.COMPANY_ADMIN)
        self.assertEqual(u.company_id, company_c.id)

    def test_company_admin_can_create_employee_own_company(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.post("/api/accounts/users/", {"email": "nouvel@a.dz", "password": PASSWORD,
                                            "first_name": "Nouvel", "last_name": "Employe",
                                            "role": User.Role.EMPLOYEE}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        u = User.objects.get(email="nouvel@a.dz")
        self.assertEqual(u.role, User.Role.EMPLOYEE)
        self.assertEqual(u.company_id, self.comp_a.id)

    def test_company_admin_can_create_hr_manager(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.post("/api/accounts/users/", {"email": "hr@a.dz", "password": PASSWORD,
                                            "first_name": "RH", "last_name": "Manager",
                                            "role": User.Role.HR_MANAGER}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        u = User.objects.get(email="hr@a.dz")
        self.assertEqual(u.role, User.Role.HR_MANAGER)
        self.assertEqual(u.company_id, self.comp_a.id)

    def test_company_admin_cannot_create_company_admin(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.post("/api/accounts/users/", {"email": "ca2@a.dz", "password": PASSWORD,
                                            "first_name": "X", "last_name": "Y",
                                            "role": User.Role.COMPANY_ADMIN}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(User.objects.filter(email="ca2@a.dz").exists())

    def test_company_admin_cannot_create_superadmin(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.post("/api/accounts/users/", {"email": "sa2@a.dz", "password": PASSWORD,
                                            "first_name": "X", "last_name": "Y",
                                            "role": User.Role.SUPER_ADMIN}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(User.objects.filter(email="sa2@a.dz").exists())

    def test_employee_cannot_create_account(self):
        c = AuthClient()
        c.login("emp@a.dz")
        r = c.post("/api/accounts/users/", {"email": "x@a.dz", "password": PASSWORD,
                                            "role": User.Role.EMPLOYEE}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_payroll_manager_cannot_create_account(self):
        c = AuthClient()
        c.login("payroll@a.dz")
        r = c.post("/api/accounts/users/", {"email": "x@a.dz", "password": PASSWORD,
                                            "role": User.Role.EMPLOYEE}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_payroll_manager_uses_unified_payroll_and_accounting_role(self):
        self.assertNotIn("accountant", User.Role.values)
        c = AuthClient()
        c.login("payroll@a.dz")
        r = c.get("/api/payslips/")
        self.assertEqual(r.status_code, 200, r.content)

    def test_auditor_cannot_modify_data(self):
        c = AuthClient()
        c.login("aud@a.dz")
        r = c.patch(f"/api/accounts/users/{self.emp_a.id}/", {"first_name": "Hack"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_admin_cannot_view_users_of_other_company(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.get("/api/accounts/users/")
        self.assertEqual(r.status_code, 200, r.content)
        emails = [u["email"] for u in r.json()]
        self.assertIn("emp@a.dz", emails)
        self.assertNotIn("emp@b.dz", emails)
        self.assertNotIn("admin@b.dz", emails)

    def test_admin_cannot_modify_user_of_other_company(self):
        # crée un employé chez B
        c = AuthClient()
        c.login("admin@b.dz")
        r = c.post("/api/accounts/users/", {"email": "empb@b.dz", "password": PASSWORD,
                                            "role": User.Role.EMPLOYEE}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        emp_b = User.objects.get(email="empb@b.dz")

        c2 = AuthClient()
        c2.login("admin@a.dz")
        r = c2.patch(f"/api/accounts/users/{emp_b.id}/", {"first_name": "Hack"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    # --- activation / désactivation -------------------------------------------

    def test_disabled_company_user_cannot_login(self):
        c = AuthClient()
        self.comp_a.is_active = False
        self.comp_a.save()
        try:
            r = c.post("/api/auth/login/", {"email": "emp@a.dz", "password": PASSWORD},
                       format="json", HTTP_X_CSRFTOKEN=self._csrf(c))
            self.assertEqual(r.status_code, 400, r.content)
            self.assertEqual(r.json()["code"], "company_disabled")
        finally:
            self.comp_a.is_active = True
            self.comp_a.save()

    def _csrf(self, client):
        client.get("/api/auth/csrf/")
        tok = client.cookies.get("csrftoken")
        return tok.value if tok else ""

    def test_disabled_user_cannot_login(self):
        c = AuthClient()
        tok = self._csrf(c)
        self.emp_a.is_active = False
        self.emp_a.save()
        try:
            r = c.post("/api/auth/login/", {"email": "emp@a.dz", "password": PASSWORD},
                       format="json", HTTP_X_CSRFTOKEN=tok)
            self.assertEqual(r.status_code, 400, r.content)
            self.assertEqual(r.json()["code"], "account_disabled")
        finally:
            self.emp_a.is_active = True
            self.emp_a.save()

    def test_admin_can_deactivate_and_activate_own_company_user(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.post(f"/api/accounts/users/{self.emp_a.id}/deactivate/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.emp_a.refresh_from_db()
        self.assertFalse(self.emp_a.is_active)
        r = c.post(f"/api/accounts/users/{self.emp_a.id}/activate/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.emp_a.refresh_from_db()
        self.assertTrue(self.emp_a.is_active)

    def test_admin_cannot_deactivate_self_if_last_admin(self):
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.post(f"/api/accounts/users/{self.admin_a.id}/deactivate/", {}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()["code"], "last_admin")
        self.admin_a.refresh_from_db()
        self.assertTrue(self.admin_a.is_active)

    # --- élévation de privilèges ---------------------------------------------

    def test_user_cannot_change_own_role_or_company(self):
        # Un administrateur d'entreprise ne peut pas s'auto-élever (ni changer d'entreprise).
        c = AuthClient()
        c.login("admin@a.dz")
        r = c.patch(f"/api/accounts/users/{self.admin_a.id}/",
                    {"role": User.Role.SUPER_ADMIN, "company": self.comp_b.id}, format="json")
        self.assertEqual(r.status_code, 403, r.content)
        self.admin_a.refresh_from_db()
        self.assertEqual(self.admin_a.role, User.Role.COMPANY_ADMIN)
        self.assertEqual(self.admin_a.company_id, self.comp_a.id)

    # --- relation Employee <-> User préservée ---------------------------------

    def test_employee_user_relation_preserved(self):
        service = Service.objects.create(name="Comptabilité")
        emp = Employee.objects.create(first_name="Z", last_name="Z", email="z@x.dz", service=service,
                                      company=self.comp_a)
        u = make_user("z@x.dz", User.Role.EMPLOYEE, self.comp_a)
        u.employee = emp
        u.save()
        self.assertEqual(u.employee_id, emp.id)
        self.assertEqual(u.company_id, self.comp_a.id)
