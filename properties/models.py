from django.db import models

# Create your models here.

class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Companies"


class Property(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="properties")
    name = models.CharField(max_length=255)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    class Meta:
        verbose_name_plural = "Properties"


class ApartmentUnit(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    unit_number = models.CharField(max_length=50)
    bedrooms = models.PositiveIntegerField()
    bathrooms = models.PositiveIntegerField()
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_occupied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Unit {self.unit_number} - {self.property.name}"

    class Meta:
        unique_together = ('property', 'unit_number')
        verbose_name_plural = "Apartment Units"
