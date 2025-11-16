from django.contrib import admin
from .models import MiscCharge, Employee

@admin.register(MiscCharge)
class MiscChargeAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'amount', 'created_by')
    list_filter = ('category', 'date')
    search_fields = ('description',)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'monthly_salary', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
