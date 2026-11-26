from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models


class Company(models.Model):
    """Une entreprise cliente du logiciel HRMS (multi-tenant)."""

    class LegalForm(models.TextChoices):
        SARL = "SARL", "SARL"
        SA = "SA", "SA"
        SAS = "SAS", "SAS"
        SNC = "SNC", "SNC"
        SCS = "SCS", "SCS"
        SOLE_PROPRIETORSHIP = "entreprise_individuelle", "Entreprise individuelle"
        OTHER = "autre", "Autre"

    # Identité juridique
    legal_name = models.CharField("dénomination sociale", max_length=200)
    acronym = models.CharField("sigle", max_length=20, blank=True)
    legal_form = models.CharField("forme juridique", max_length=30, choices=LegalForm.choices, default=LegalForm.OTHER)
    legal_creation_date = models.DateField("date de création juridique", null=True, blank=True)
    created_at = models.DateTimeField("enregistrée le", auto_now_add=True)

    # Informations générales
    activity_sector = models.CharField("secteur d'activité", max_length=100, blank=True)
    official_description = models.TextField("description officielle", blank=True)
    nationality = models.CharField("nationalité", max_length=100, blank=True)

    # Informations administratives
    tax_identification_number = models.CharField(
        "NIU / numéro fiscal",
        max_length=50,
        blank=True,
        validators=[RegexValidator(r"^[A-Za-z0-9 \-/.]+$", "Numéro d'identification invalide.")],
        help_text="Format adapté au pays de l'entreprise.",
    )

    # Localisation
    country = models.CharField("pays", max_length=100, blank=True)
    city = models.CharField("ville", max_length=100, blank=True)
    district = models.CharField("quartier", max_length=100, blank=True)
    postal_box = models.CharField("boîte postale", max_length=20, blank=True)

    # Présence numérique
    website = models.URLField("site Internet", blank=True)
    logo = models.ImageField("logo", upload_to="company_logos/", blank=True, null=True)

    # Direction
    director_first_name = models.CharField("prénom du dirigeant", max_length=100, blank=True)
    director_last_name = models.CharField("nom du dirigeant", max_length=100, blank=True)

    # Gestion
    is_active = models.BooleanField("active", default=True)
    updated_at = models.DateTimeField("modifiée le", auto_now=True)

    class Meta:
        ordering = ["legal_name"]
        verbose_name = "entreprise"
        verbose_name_plural = "entreprises"

    def __str__(self):
        return self.legal_name or self.acronym or f"Entreprise #{self.pk}"


class CompanyLeader(models.Model):
    """Administrateur ou dirigeant d'une entreprise (fiche indépendante d'un compte utilisateur)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="leaders")
    first_name = models.CharField("prénom", max_length=100)
    last_name = models.CharField("nom", max_length=100)
    position = models.CharField("fonction", max_length=100, blank=True)
    created_at = models.DateTimeField("enregistré le", auto_now_add=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "dirigeant"
        verbose_name_plural = "dirigeants"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class HRMSUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "super_admin")
        extra_fields["company"] = None
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    """Un login. Rôles centralisés multi-entreprises. Un utilisateur ordinaire est rattaché à une entreprise."""

    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Superadministrateur"
        COMPANY_ADMIN = "company_admin", "Administrateur d'entreprise"
        HR_MANAGER = "hr_manager", "Responsable RH"
        PAYROLL_MANAGER = "payroll_manager", "Responsable paie et comptabilité"
        MANAGER = "manager", "Responsable de département"
        EMPLOYEE = "employee", "Employé"
        AUDITOR = "auditor", "Auditeur"
        # Anciennes valeurs conservées pour la compatibilité avec les comptes existants.
        HR = "hr", "RH (ancien)"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    company = models.ForeignKey(
        Company,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
        verbose_name="entreprise",
    )
    employee = models.OneToOneField("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="user")
    must_change_password = models.BooleanField(default=False)
    objects = HRMSUserManager()

    @property
    def is_super_admin(self) -> bool:
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_company_admin(self) -> bool:
        return self.role == self.Role.COMPANY_ADMIN

    @property
    def is_hr_manager(self) -> bool:
        return self.role == self.Role.HR_MANAGER

    @property
    def is_payroll_manager(self) -> bool:
        return self.role == self.Role.PAYROLL_MANAGER

    @property
    def is_manager(self) -> bool:
        return self.role == self.Role.MANAGER

    @property
    def is_employee_role(self) -> bool:
        return self.role == self.Role.EMPLOYEE

    @property
    def is_auditor(self) -> bool:
        return self.role == self.Role.AUDITOR

    @property
    def is_hr(self) -> bool:
        return self.is_active and (self.role in (self.Role.HR, self.Role.HR_MANAGER) or self.is_superuser)

    @property
    def ordinary_roles(self):
        """Rôles qu'un COMPANY_ADMIN est autorisé à créer."""
        return (
            self.Role.HR_MANAGER,
            self.Role.PAYROLL_MANAGER,
            self.Role.MANAGER,
            self.Role.EMPLOYEE,
            self.Role.AUDITOR,
        )

    def can_manage_user(self, other: "User") -> bool:
        """Règle d'élévation de privilèges : un compte ne gère que ses pairs de sa propre entreprise."""
        if self.is_super_admin or self.is_superuser:
            return True
        if self.is_company_admin:
            if other.role in (self.Role.SUPER_ADMIN, self.Role.COMPANY_ADMIN):
                return False
            return self.company_id is not None and other.company_id == self.company_id
        return False

    def __str__(self):
        return self.email or self.username
