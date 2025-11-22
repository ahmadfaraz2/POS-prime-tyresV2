from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime

from balancesheet.models import LedgerEntry


class Command(BaseCommand):
    help = 'Backdate ledger entries based on their source_type/source_id mapping to source record dates.'

    def handle(self, *args, **options):
        updated = 0
        for le in LedgerEntry.objects.filter(source_type__isnull=False).all():
            # only update entries with a source mapped
            st = le.source_type
            sid = le.source_id
            if not st or not sid:
                continue
            try:
                if st == 'purchase':
                    from vendor.models import Purchase
                    obj = Purchase.objects.filter(id=sid).first()
                    if obj:
                        le.date = obj.date
                        le.save(update_fields=['date'])
                        updated += 1
                elif st in ('sale', 'sale_item'):
                    from sales.models import Sale
                    obj = Sale.objects.filter(id=sid).first()
                    if obj:
                        le.date = obj.date
                        le.save(update_fields=['date'])
                        updated += 1
                elif st == 'installment_payment':
                    from sales.models import InstallmentPayment
                    obj = InstallmentPayment.objects.filter(id=sid).first()
                    if obj:
                        # payment_date is a date field; convert to datetime at midnight
                        le.date = timezone.make_aware(datetime.combine(obj.payment_date, datetime.min.time()))
                        le.save(update_fields=['date'])
                        updated += 1
                elif st in ('customer_return', 'customer_return_item'):
                    from returns.models import CustomerReturn
                    obj = CustomerReturn.objects.filter(id=sid).first()
                    if obj:
                        le.date = obj.date
                        le.save(update_fields=['date'])
                        updated += 1
                elif st in ('vendor_return',):
                    from returns.models import VendorReturn
                    obj = VendorReturn.objects.filter(id=sid).first()
                    if obj:
                        le.date = obj.date
                        le.save(update_fields=['date'])
                        updated += 1
                elif st == 'misc_charge':
                    from sales.models import MiscCharge
                    obj = MiscCharge.objects.filter(id=sid).first()
                    if obj:
                        # misc charge has a date field
                        le.date = timezone.make_aware(datetime.combine(obj.date, datetime.min.time()))
                        le.save(update_fields=['date'])
                        updated += 1
            except Exception:
                continue

        self.stdout.write(f'Backdated {updated} ledger entries.')
