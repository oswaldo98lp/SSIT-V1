"""Custom User Model and Scope Resolution for SSIT 2.0."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager where email is the unique identifier for auth."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("has_global_scope", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Extiende AbstractUser con número de empleado, centro, región y alcance.
    """
    username = None  # Autenticación exclusivamente por email
    email = models.EmailField(unique=True, verbose_name="Correo electrónico")
    employee_number = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Número de empleado",
    )
    full_name = models.CharField(max_length=255, verbose_name="Nombre completo")
    position = models.CharField(max_length=128, blank=True, default="", verbose_name="Puesto")

    center = models.ForeignKey(
        "org.Center",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Centro asignado",
    )
    region = models.ForeignKey(
        "org.Region",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="primary_users",
        verbose_name="Región asignada",
    )
    has_global_scope = models.BooleanField(
        default=False,
        verbose_name="Alcance global (todas las regiones)",
        help_text="Permite consultar y operar sobre todas las regiones del sistema.",
    )
    extra_regions = models.ManyToManyField(
        "org.Region",
        blank=True,
        related_name="extra_scope_users",
        verbose_name="Regiones adicionales permitidas",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def allowed_regions(self):
        """
        Calcula el conjunto de regiones permitidas para este usuario:
        - Si tiene has_global_scope o es superusuario: todas las regiones activas.
        - Si pertenece al rol GERENTE_ZONA: todas las regiones de su zona + extra_regions.
        - En cualquier otro caso: su propia región + extra_regions.
        """
        from apps.org.models import Region

        if self.is_superuser or self.has_global_scope:
            return Region.objects.all()

        is_zone_manager = self.groups.filter(name="GERENTE_ZONA").exists()
        region_ids = set()

        if self.region_id:
            region_ids.add(self.region_id)

        if is_zone_manager and self.region and self.region.zone_id:
            zone_regions = Region.objects.filter(zone_id=self.region.zone_id).values_list("id", flat=True)
            region_ids.update(zone_regions)

        # Agregar extra_regions asignadas
        extra_ids = self.extra_regions.values_list("id", flat=True)
        region_ids.update(extra_ids)

        return Region.objects.filter(id__in=region_ids)
