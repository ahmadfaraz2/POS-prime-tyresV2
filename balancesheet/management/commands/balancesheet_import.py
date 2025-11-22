from django.core.management.base import BaseCommand
from decimal import Decimal
from django.db import transaction

from balancesheet.models import Account, LedgerEntry
from products.models import Product
from sales.models import Sale, SaleItem, InstallmentPayment, MiscCharge
from vendor.models import Purchase, PurchaseItem
from returns.models import CustomerReturn, VendorReturn, ReturnItem


def get_account(code, defaults):
    obj, _ = Account.objects.get_or_create(code=code, defaults=defaults)
    return obj


class Command(BaseCommand):
    help = 'Import transactions into the balancesheet ledger. Use --apply to write entries.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write entries to ledger. Without this runs dry-run.')

    def handle(self, *args, **options):
        apply_changes = options.get('apply')

        # Ensure core accounts exist
        cash = get_account('CASH', {'name': 'Cash', 'account_type': Account.ASSET})
        inventory = get_account('INVENTORY', {'name': 'Inventory', 'account_type': Account.ASSET})
        ar = get_account('AR', {'name': 'Accounts Receivable', 'account_type': Account.ASSET})
        ap = get_account('AP', {'name': 'Accounts Payable', 'account_type': Account.LIABILITY})
        sales = get_account('SALES', {'name': 'Sales Revenue', 'account_type': Account.REVENUE})
        cogs = get_account('COGS', {'name': 'Cost of Goods Sold', 'account_type': Account.EXPENSE})
        equity = get_account('EQUITY', {'name': 'Equity', 'account_type': Account.EQUITY})

        actions = []

        # Purchases -> Inventory (debit), AP (credit)
        for p in Purchase.objects.prefetch_related('items__product').all():
            exists = LedgerEntry.objects.filter(source_type='purchase', source_id=p.id).exists()
            total = sum((it.unit_cost or Decimal('0')) * (it.quantity or 0) for it in p.items.all()) + (p.transport_cost or Decimal('0'))
            if total == 0:
                continue
            actions.append((p, 'purchase', total, exists))

        # Sales -> AR (debit), Sales (credit); COGS and Inventory adjustments per item
        for s in Sale.objects.prefetch_related('items__product').filter(is_completed=True):
            exists = LedgerEntry.objects.filter(source_type='sale', source_id=s.id).exists()
            total = s.total_amount or Decimal('0')
            actions.append((s, 'sale', total, exists))

        # Installment payments -> Cash (debit), AR (credit)
        for pay in InstallmentPayment.objects.select_related('plan__sale').all():
            exists = LedgerEntry.objects.filter(source_type='installment_payment', source_id=pay.id).exists()
            amt = pay.amount_paid or Decimal('0')
            actions.append((pay, 'installment_payment', amt, exists))

        # Customer returns -> reverse sales and adjust inventory
        for cret in CustomerReturn.objects.prefetch_related('items__product').all():
            exists = LedgerEntry.objects.filter(source_type='customer_return', source_id=cret.id).exists()
            total = cret.total_amount or Decimal('0')
            actions.append((cret, 'customer_return', total, exists))

        # Vendor returns -> reduce AP and inventory
        for vret in VendorReturn.objects.prefetch_related('items__product').all():
            exists = LedgerEntry.objects.filter(source_type='vendor_return', source_id=vret.id).exists()
            total = vret.total_amount or Decimal('0')
            actions.append((vret, 'vendor_return', total, exists))

        # Show summary
        self.stdout.write('Planned import actions:')
        for obj, typ, amt, exists in actions:
            status = 'SKIP(existing)' if exists else 'NEW'
            self.stdout.write(f'  [{status}] {typ} #{getattr(obj, "id", "?")} amount Rs {amt}')

        if not apply_changes:
            self.stdout.write('\nDry-run complete. Run with --apply to write ledger entries.')
            return

        # Also include MiscCharge entries
        for mc in MiscCharge.objects.all():
            exists = LedgerEntry.objects.filter(source_type='misc_charge', source_id=mc.id).exists()
            amt = mc.amount or Decimal('0')
            if amt == 0:
                continue
            actions.append((mc, 'misc_charge', amt, exists))

        # Show summary (updated)
        self.stdout.write('\nUpdated planned import actions:')
        for obj, typ, amt, exists in actions:
            status = 'SKIP(existing)' if exists else 'NEW'
            self.stdout.write(f'  [{status}] {typ} #{getattr(obj, "id", "?")} amount Rs {amt}')

        # Apply changes
        created = 0
        with transaction.atomic():
            for obj, typ, amt, exists in actions:
                if exists or amt == 0:
                    continue
                # determine date for the ledger entries from source when available
                entry_date = None
                try:
                    if hasattr(obj, 'date'):
                        entry_date = obj.date
                    elif hasattr(obj, 'payment_date'):
                        entry_date = obj.payment_date
                except Exception:
                    entry_date = None

                if typ == 'purchase':
                    p = obj
                    # Debit Inventory, Credit AP
                    LedgerEntry.objects.create(account=inventory, description=f'Purchase #{p.id}', debit=amt, credit=Decimal('0'), source_type='purchase', source_id=p.id, date=entry_date)
                    LedgerEntry.objects.create(account=ap, description=f'Purchase #{p.id}', debit=Decimal('0'), credit=amt, source_type='purchase', source_id=p.id, date=entry_date)
                    created += 2
                elif typ == 'sale':
                    s = obj
                    # Debit AR, Credit Sales
                    LedgerEntry.objects.create(account=ar, description=f'Sale #{s.id}', debit=amt, credit=Decimal('0'), source_type='sale', source_id=s.id, date=entry_date)
                    LedgerEntry.objects.create(account=sales, description=f'Sale #{s.id}', debit=Decimal('0'), credit=amt, source_type='sale', source_id=s.id, date=entry_date)
                    created += 2
                    # For each sale item, create COGS / Inventory entries
                    for it in s.items.all():
                        cost = (it.product.purchasing_price or Decimal('0')) * (it.quantity or 0)
                        if cost == 0:
                            continue
                        LedgerEntry.objects.create(account=cogs, description=f'SaleItem #{it.id} COGS', debit=cost, credit=Decimal('0'), source_type='sale_item', source_id=it.id, date=entry_date)
                        LedgerEntry.objects.create(account=inventory, description=f'SaleItem #{it.id} reduce inventory', debit=Decimal('0'), credit=cost, source_type='sale_item', source_id=it.id, date=entry_date)
                        created += 2
                elif typ == 'installment_payment':
                    pay = obj
                    amt = pay.amount_paid or Decimal('0')
                    LedgerEntry.objects.create(account=cash, description=f'InstallmentPayment #{pay.id}', debit=amt, credit=Decimal('0'), source_type='installment_payment', source_id=pay.id, date=entry_date)
                    LedgerEntry.objects.create(account=ar, description=f'InstallmentPayment #{pay.id}', debit=Decimal('0'), credit=amt, source_type='installment_payment', source_id=pay.id, date=entry_date)
                    created += 2
                elif typ == 'customer_return':
                    cret = obj
                    # Debit Sales (reduce revenue), Credit AR (or Cash if refunded) - assume reduce AR
                    LedgerEntry.objects.create(account=sales, description=f'CustomerReturn #{cret.id}', debit=cret.total_amount, credit=Decimal('0'), source_type='customer_return', source_id=cret.id, date=entry_date)
                    LedgerEntry.objects.create(account=ar, description=f'CustomerReturn #{cret.id}', debit=Decimal('0'), credit=cret.total_amount, source_type='customer_return', source_id=cret.id, date=entry_date)
                    created += 2
                    # Return items -> Inventory (debit), COGS (credit reverse)
                    for it in cret.items.all():
                        amt_item = (it.unit_cost or Decimal('0')) * (it.quantity or 0)
                        if amt_item == 0:
                            continue
                        LedgerEntry.objects.create(account=inventory, description=f'CustomerReturnItem #{it.id}', debit=amt_item, credit=Decimal('0'), source_type='customer_return_item', source_id=it.id, date=entry_date)
                        LedgerEntry.objects.create(account=cogs, description=f'CustomerReturnItem #{it.id}', debit=Decimal('0'), credit=amt_item, source_type='customer_return_item', source_id=it.id, date=entry_date)
                        created += 2
                elif typ == 'vendor_return':
                    vret = obj
                    # Debit AP (reduce liability), Credit Inventory (decrease inventory)
                    LedgerEntry.objects.create(account=ap, description=f'VendorReturn #{vret.id}', debit=vret.total_amount, credit=Decimal('0'), source_type='vendor_return', source_id=vret.id, date=entry_date)
                    LedgerEntry.objects.create(account=inventory, description=f'VendorReturn #{vret.id}', debit=Decimal('0'), credit=vret.total_amount, source_type='vendor_return', source_id=vret.id, date=entry_date)
                    created += 2
                elif typ == 'misc_charge':
                    mc = obj
                    # Debit expense, Credit cash (assume paid in cash)
                    misc_acc = get_account(f'MISC_{mc.category}', {'name': f'Misc - {mc.get_category_display()}', 'account_type': Account.EXPENSE})
                    LedgerEntry.objects.create(account=misc_acc, description=f'MiscCharge #{mc.id} {mc.category}', debit=amt, credit=Decimal('0'), source_type='misc_charge', source_id=mc.id, date=entry_date)
                    LedgerEntry.objects.create(account=cash, description=f'MiscCharge #{mc.id} {mc.category}', debit=Decimal('0'), credit=amt, source_type='misc_charge', source_id=mc.id, date=entry_date)
                    created += 2

        self.stdout.write(f'Imported ledger entries: {created}')
