from django.contrib import admin
from .models import CustomerReturn, VendorReturn, ReturnItem


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0


@admin.register(CustomerReturn)
class CustomerReturnAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'date', 'total_amount')
    inlines = [ReturnItemInline]


@admin.register(VendorReturn)
class VendorReturnAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendor', 'date', 'total_amount')
    inlines = [ReturnItemInline]
