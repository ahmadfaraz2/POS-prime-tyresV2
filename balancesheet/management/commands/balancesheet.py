from django.core.management.base import BaseCommand
from decimal import Decimal
from django.db.models import Sum

from balancesheet.models import Account


class Command(BaseCommand):
    help = 'Print balance sheet from ledger entries. Use --seed to create default accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', action='store_true', help='Create default accounts if missing')

    def handle(self, *args, **options):
        if options.get('seed'):
            self.seed_accounts()

        accounts = Account.objects.all().annotate(
            total_debit=Sum('entries__debit'),
            total_credit=Sum('entries__credit')
        )

        assets = []
        liabilities = []
        equity = []
        revenue = []
        expense = []

        for a in accounts:
            td = a.total_debit or Decimal('0')
            tc = a.total_credit or Decimal('0')
            # For assets and expenses, normal balance is debit; for liabilities/equity/revenue it's credit
            if a.account_type in (Account.ASSET, Account.EXPENSE):
                bal = td - tc
            else:
                bal = tc - td
            # quantize for neatness
            bal = Decimal(bal).quantize(Decimal('0.01'))

            if a.account_type == Account.ASSET:
                assets.append((a, bal))
            elif a.account_type == Account.LIABILITY:
                liabilities.append((a, bal))
            elif a.account_type == Account.EQUITY:
                equity.append((a, bal))
            elif a.account_type == Account.REVENUE:
                revenue.append((a, bal))
            elif a.account_type == Account.EXPENSE:
                expense.append((a, bal))

        assets_total = sum(b for _, b in assets) if assets else Decimal('0')
        liabilities_total = sum(b for _, b in liabilities) if liabilities else Decimal('0')
        equity_total = sum(b for _, b in equity) if equity else Decimal('0')
        revenue_total = sum(b for _, b in revenue) if revenue else Decimal('0')
        expense_total = sum(b for _, b in expense) if expense else Decimal('0')

        net_income = revenue_total - expense_total
        equity_with_income = equity_total + net_income

        self.stdout.write('*** Balance Sheet (Project) ***')
        self.stdout.write('\nASSETS:')
        for a, b in assets:
            self.stdout.write(f'  {a.name} ({a.code or a.pk}): Rs {b}')
        self.stdout.write(f'  Total Assets: Rs {assets_total}\n')

        self.stdout.write('LIABILITIES:')
        for a, b in liabilities:
            self.stdout.write(f'  {a.name} ({a.code or a.pk}): Rs {b}')
        self.stdout.write(f'  Total Liabilities: Rs {liabilities_total}\n')

        self.stdout.write('EQUITY:')
        for a, b in equity:
            self.stdout.write(f'  {a.name} ({a.code or a.pk}): Rs {b}')
        self.stdout.write(f'  Equity (direct accounts): Rs {equity_total}')
        self.stdout.write(f'  Net income (Revenue - Expense): Rs {net_income}')
        self.stdout.write(f'  Total Equity (incl. Net Income): Rs {equity_with_income}\n')

        self.stdout.write(f'Total Liabilities + Equity: Rs {liabilities_total + equity_with_income}')
        self.stdout.write(f'Total Assets: Rs {assets_total}')

        diff = (assets_total - (liabilities_total + equity_with_income)).quantize(Decimal('0.01'))
        self.stdout.write(f'Balance check (Assets - (Liabilities + Equity)): Rs {diff}')
        if diff != Decimal('0.00'):
            self.stderr.write('\nWarning: Balance sheet does not balance. This usually means transactions are not yet imported into the ledger or double-entry entries are missing.\n')

    def seed_accounts(self):
        defaults = [
            ('Cash', 'CASH', Account.ASSET),
            ('Inventory', 'INVENTORY', Account.ASSET),
            ('Accounts Receivable', 'AR', Account.ASSET),
            ('Accounts Payable', 'AP', Account.LIABILITY),
            ('Sales Revenue', 'SALES', Account.REVENUE),
            ('Cost of Goods Sold', 'COGS', Account.EXPENSE),
            ('Equity', 'EQUITY', Account.EQUITY),
        ]
        created = 0
        for name, code, typ in defaults:
            obj, created_flag = Account.objects.get_or_create(code=code, defaults={'name': name, 'account_type': typ})
            if created_flag:
                created += 1
        self.stdout.write(f'Seeded {created} accounts.')
