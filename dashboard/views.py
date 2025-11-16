from decimal import Decimal
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.shortcuts import render
from django.utils import timezone

from products.models import Product
from customers.models import Customer
from sales.models import Sale, InstallmentPlan, SaleItem, MiscCharge
from sales.models import Employee


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

    # Profit calculations
    profit_expr = ExpressionWrapper((F('unit_price') - F('product__purchasing_price')) * F('quantity'), output_field=DecimalField(max_digits=14, decimal_places=2))

    sales_today_profit = SaleItem.objects.filter(sale__date__gte=today_start).aggregate(s=Sum(profit_expr))['s'] or Decimal('0')
    sales_this_week_profit = SaleItem.objects.filter(sale__date__gte=week_start).aggregate(s=Sum(profit_expr))['s'] or Decimal('0')
    sales_this_month_profit = SaleItem.objects.filter(sale__date__gte=month_start).aggregate(s=Sum(profit_expr))['s'] or Decimal('0')

    total_gross_profit = SaleItem.objects.filter(sale__is_completed=True).aggregate(s=Sum(profit_expr))['s'] or Decimal('0')

    # Misc charges sums (overall and for current month)
    total_misc_charges = MiscCharge.objects.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    month_misc_charges = MiscCharge.objects.filter(date__gte=month_start.date()).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # Breakdown by category
    transport_total = MiscCharge.objects.filter(category='TRANSPORT').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    salary_total = MiscCharge.objects.filter(category='SALARY').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    month_transport = MiscCharge.objects.filter(category='TRANSPORT', date__gte=month_start.date()).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    month_salary = MiscCharge.objects.filter(category='SALARY', date__gte=month_start.date()).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # Net profit = Gross profit - misc charges
    total_net_profit = total_gross_profit - total_misc_charges

    # Employee payroll
    monthly_payroll = Employee.objects.filter(is_active=True).aggregate(s=Sum('monthly_salary'))['s'] or Decimal('0')

    # Net profit for current month subtracting payroll and month misc charges (transport/salary)
    net_profit_this_month = sales_this_month_profit - monthly_payroll - month_misc_charges - month_transport

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
        # Profit context for template
        'sales_today_profit': sales_today_profit,
        'sales_this_week_profit': sales_this_week_profit,
        'sales_this_month_profit': sales_this_month_profit,
        'total_gross_profit': total_gross_profit,
    'total_misc_charges': total_misc_charges,
    'total_net_profit': total_net_profit,
    'transport_total': transport_total,
    'salary_total': salary_total,
    'month_transport': month_transport,
    'month_salary': month_salary,
        'monthly_payroll': monthly_payroll,
        'net_profit_this_month': net_profit_this_month,
    }
    return render(request, 'dashboard/dashboard.html', ctx)
