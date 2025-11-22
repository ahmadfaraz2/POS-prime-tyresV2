from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from balancesheet.models import Account


@login_required
def balancesheet_view(request):
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
        if a.account_type in (Account.ASSET, Account.EXPENSE):
            bal = td - tc
        else:
            bal = tc - td
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

    context = {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'assets_total': assets_total,
        'liabilities_total': liabilities_total,
        'equity_total': equity_total,
        'revenue_total': revenue_total,
        'expense_total': expense_total,
        'net_income': net_income,
        'equity_with_income': equity_with_income,
    }
    return render(request, 'balancesheet/list.html', context)
