from decimal import Decimal
from django.db import models
from django.conf import settings


class BaseReturn(models.Model):
    """Abstract base for returns."""
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='%(class)s_returns')
    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True


class CustomerReturn(BaseReturn):
    customer = models.ForeignKey('customers.Customer', on_delete=models.PROTECT, related_name='returns')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"CustomerReturn #{self.id} - {self.customer}"


class VendorReturn(BaseReturn):
    vendor = models.ForeignKey('vendor.Vendor', on_delete=models.PROTECT, related_name='returns')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"VendorReturn #{self.id} - {self.vendor}"


class ReturnItem(models.Model):
    """Items for both types of returns. One of customer_return or vendor_return will be set."""
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='return_items')
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    customer_return = models.ForeignKey(CustomerReturn, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    vendor_return = models.ForeignKey(VendorReturn, on_delete=models.CASCADE, related_name='items', null=True, blank=True)

    def save(self, *args, **kwargs):
        self.subtotal = (self.unit_cost or Decimal('0')) * (self.quantity or 0)
        super().save(*args, **kwargs)
