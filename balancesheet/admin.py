from django.contrib import admin
from .models import Account, LedgerEntry


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'account_type', 'created_at')
    list_filter = ('account_type',)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'account', 'debit', 'credit', 'source_type', 'source_id')
    list_filter = ('account', 'source_type')
    search_fields = ('description',)
