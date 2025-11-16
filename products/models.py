from decimal import Decimal
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True, null=True)
    size = models.CharField(max_length=64, blank=True, null=True)
    type = models.CharField(max_length=128, blank=True, null=True)
    # selling price
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # purchasing price (cost price) to calculate profit
    purchasing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def selling_price(self) -> Decimal:
        """Alias for the current selling price (keeps existing DB field name `price`)."""
        return self.price

    @property
    def profit(self) -> Decimal:
        """Profit per unit (selling - purchasing). Returns Decimal."""
        try:
            return (self.price - self.purchasing_price)
        except Exception:
            return Decimal('0')
