from django.conf import settings
from django.db import models


class Sale(models.Model):
    PAYMENT_TYPE_CHOICES = [(s, s.title()) for s in ('FULL', 'INSTALLMENT')]
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='sales')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_sales')
    date = models.DateTimeField(auto_now_add=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Sale #{self.id} - {self.customer.name}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='sale_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)


class InstallmentPlan(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
    ]
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name='installment_plan')
    total_installments = models.PositiveIntegerField()
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    first_due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)


class InstallmentPayment(models.Model):
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=True)
