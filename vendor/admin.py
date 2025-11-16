from django.contrib import admin
from .models import Vendor, Purchase, PurchaseItem


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email')
    search_fields = ('name', 'phone', 'email')


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendor', 'date', 'total_amount', 'transport_cost', 'is_received')
    list_filter = ('is_received', 'date')
    inlines = [PurchaseItemInline]
