from django.db import models
from django.utils import timezone
from decimal import Decimal


class Account(models.Model):
    ASSET = 'ASSET'
    LIABILITY = 'LIABILITY'
    EQUITY = 'EQUITY'
    REVENUE = 'REVENUE'
    EXPENSE = 'EXPENSE'

    ACCOUNT_TYPES = [
        (ASSET, 'Asset'),
        (LIABILITY, 'Liability'),
        (EQUITY, 'Equity'),
        (REVENUE, 'Revenue'),
        (EXPENSE, 'Expense'),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=32, blank=True, null=True, unique=True)
    account_type = models.CharField(max_length=16, choices=ACCOUNT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['account_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.account_type})"


class LedgerEntry(models.Model):
    account = models.ForeignKey(Account, related_name='entries', on_delete=models.CASCADE)
    # allow setting dates explicitly for backdating ledger entries
    date = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    # Optional link to source model for traceability
    source_type = models.CharField(max_length=100, blank=True, null=True)
    source_id = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.date.date()} {self.account.name}: D{self.debit} C{self.credit}"
