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
    # Previously we stored a fixed schedule here. New behaviour: do not pre-create
    # specific installment entries. The plan now acts as a single record that
    # groups ad-hoc `InstallmentPayment` records against the `Sale`.
    # Keep minimal metadata and status.
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)


class InstallmentPayment(models.Model):
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=True)


class MiscCharge(models.Model):
    CATEGORY_CHOICES = [
        ('TRANSPORT', 'Transport'),
        ('SALARY', 'Salary'),
        ('SUPPLIES', 'Supplies'),
        ('OTHER', 'Other'),
    ]
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='misc_charges')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_category_display()} - Rs {self.amount} on {self.date}"


class Employee(models.Model):
    name = models.CharField(max_length=255)
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_active', 'name']

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"
