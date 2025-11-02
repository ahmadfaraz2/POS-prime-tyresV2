from decimal import Decimal
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render
from django.utils import timezone

from products.models import Product
from customers.models import Customer
from sales.models import Sale, InstallmentPlan


@login_required
def dashboard_view(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Sales statistics
    sales_today = Sale.objects.filter(date__gte=today_start).count()
    sales_today_revenue = Sale.objects.filter(date__gte=today_start).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    
    # Week statistics
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    sales_this_week = Sale.objects.filter(date__gte=week_start).count()
    sales_this_week_revenue = Sale.objects.filter(date__gte=week_start).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    
    # Month statistics
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sales_this_month = Sale.objects.filter(date__gte=month_start).count()
    sales_this_month_revenue = Sale.objects.filter(date__gte=month_start).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    
    # Overall statistics
    total_revenue = Sale.objects.filter(is_completed=True).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    total_products = Product.objects.count()
    total_customers = Customer.objects.count()
    low_stock_products = Product.objects.filter(stock_quantity__lte=10).count()

    # Installment statistics
    plans = InstallmentPlan.objects.all().annotate(paid=Sum('payments__amount_paid'))
    outstanding = Decimal('0')
    pending_installments = 0
    for p in plans:
        total_due = p.sale.total_amount  # Use actual sale total
        paid = p.paid or Decimal('0')
        diff = total_due - paid
        if diff > 0:
            outstanding += diff
            if p.status == 'PENDING':
                pending_installments += 1

    # Recent sales (last 5)
    recent_sales = Sale.objects.select_related('customer').order_by('-date')[:5]

    ctx = {
        'sales_today': sales_today,
        'sales_today_revenue': sales_today_revenue,
        'sales_this_week': sales_this_week,
        'sales_this_week_revenue': sales_this_week_revenue,
        'sales_this_month': sales_this_month,
        'sales_this_month_revenue': sales_this_month_revenue,
        'total_revenue': total_revenue,
        'total_products': total_products,
        'total_customers': total_customers,
        'low_stock_products': low_stock_products,
        'outstanding_installments': outstanding,
        'pending_installments': pending_installments,
        'recent_sales': recent_sales,
    }
    return render(request, 'dashboard/dashboard.html', ctx)
