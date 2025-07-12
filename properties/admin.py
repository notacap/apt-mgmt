from django.contrib import admin
from .models import Company, Property, ApartmentUnit

admin.site.register(Company)
admin.site.register(Property)
admin.site.register(ApartmentUnit)
