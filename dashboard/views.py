from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from products.models import Product
from customers.models import Customer
from sales.models import Sale, InstallmentPlan


@login_required
def dashboard_view(request):
    today = timezone.now().date()
    sales_today = Sale.objects.filter(date__date=today).count()
    revenue = Sale.objects.filter(is_completed=True).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    total_products = Product.objects.count()
    total_customers = Customer.objects.count()

    plans = InstallmentPlan.objects.all().annotate(paid=Sum('payments__amount_paid'))
    outstanding = Decimal('0')
    for p in plans:
        total_due = (p.total_installments * p.installment_amount)
        paid = p.paid or Decimal('0')
        diff = total_due - paid
        if diff > 0:
            outstanding += diff

    ctx = {
        'sales_today': sales_today,
        'revenue': revenue,
        'total_products': total_products,
        'total_customers': total_customers,
        'outstanding_installments': outstanding,
    }
    return render(request, 'dashboard/dashboard.html', ctx)
