from decimal import Decimal
from datetime import datetime, timedelta
import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Sale, InstallmentPlan, InstallmentPayment
from .models import MiscCharge
from django.shortcuts import reverse
from products.models import Product


@login_required
def sale_list(request):
    # Get filter parameter
    date_filter = request.GET.get('filter', 'all')
    
    # Start with base queryset
    qs = Sale.objects.select_related('customer').order_by('-date')
    
    # Apply date filters
    now = timezone.now()
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(date__gte=start_date)
    elif date_filter == 'week':
        start_date = now - timedelta(days=now.weekday())  # Monday of current week
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(date__gte=start_date)
    elif date_filter == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(date__gte=start_date)
    
    # Calculate totals for display
    total_sales = qs.count()
    total_revenue = qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    
    page_obj = Paginator(qs, 10).get_page(request.GET.get('page'))
    
    return render(request, 'sales/sale_list.html', {
        'page_obj': page_obj,
        'date_filter': date_filter,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
    })


@login_required
def export_sales_csv(request):
    # Get filter parameter
    date_filter = request.GET.get('filter', 'all')
    
    # Start with base queryset
    qs = Sale.objects.select_related('customer', 'created_by').prefetch_related('items__product').order_by('-date')
    
    # Apply date filters
    now = timezone.now()
    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(date__gte=start_date)
    elif date_filter == 'week':
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(date__gte=start_date)
    elif date_filter == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(date__gte=start_date)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f'sales_{date_filter}_{now.strftime("%Y%m%d_%H%M%S")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Sale ID',
        'Date',
        'Time',
        'Customer Name',
        'Customer Phone',
        'Customer Email',
        'Payment Type',
        'Total Amount (Rs)',
        'Status',
        'Processed By',
        'Items Count',
        'Items Details'
    ])
    
    # Write data
    for sale in qs:
        # Get items details
        items_details = '; '.join([
            f"{item.product.name} (Qty: {item.quantity}, Price: Rs {item.unit_price})"
            for item in sale.items.all()
        ])
        
        writer.writerow([
            sale.id,
            sale.date.strftime('%Y-%m-%d'),
            sale.date.strftime('%H:%M:%S'),
            sale.customer.name,
            sale.customer.phone or '',
            sale.customer.email or '',
            sale.get_payment_type_display(),
            str(sale.total_amount),
            'Completed' if sale.is_completed else 'Pending',
            sale.created_by.username,
            sale.items.count(),
            items_details
        ])
    
    return response


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('customer').prefetch_related('items__product'), pk=pk)
    plan = getattr(sale, 'installment_plan', None)
    if plan:
        payments = plan.payments.all().order_by('-payment_date')
        total_paid = payments.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    else:
        payments = []
        total_paid = Decimal('0')
    return render(request, 'sales/sale_detail.html', {
        'sale': sale,
        'plan': plan,
        'payments': payments,
        'total_paid': total_paid,
    })


@login_required
def installment_list(request):
    plans = InstallmentPlan.objects.select_related('sale__customer').annotate(
        paid=Sum('payments__amount_paid')
    ).order_by('-created_at')
    # Compute outstanding per plan for template
    plan_data = []
    for p in plans:
        total_due = p.sale.total_amount  # Use actual sale total, not installment_amount * count
        paid = p.paid or Decimal('0')
        outstanding = total_due - paid
        if outstanding < 0:
            outstanding = Decimal('0')
        plan_data.append({'plan': p, 'paid': paid, 'outstanding': outstanding, 'total_due': total_due})
    page_obj = Paginator(plan_data, 10).get_page(request.GET.get('page'))
    return render(request, 'sales/installment_list.html', {'page_obj': page_obj})


@login_required
def installment_payment_create(request, plan_id):
    plan = get_object_or_404(InstallmentPlan.objects.select_related('sale__customer'), pk=plan_id)
    if request.method == 'POST':
        amount_str = request.POST.get('amount')
        try:
            amount = Decimal(amount_str)
        except Exception:
            messages.error(request, 'Invalid amount.')
            return redirect('sales:installment_payment_create', plan_id=plan.id)
        
        InstallmentPayment.objects.create(plan=plan, amount_paid=amount)
        
        # Check if installment is fully paid
        total_paid = plan.payments.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
        total_due = plan.sale.total_amount
        
        if total_paid >= total_due:
            plan.status = 'PAID'
            plan.save(update_fields=['status'])
            messages.success(request, 'Payment recorded. Installment plan is now fully paid!')
        else:
            messages.success(request, 'Payment recorded.')
        
        return redirect('sales:sale_detail', pk=plan.sale.id)
    # Simple inline form
    return render(request, 'sales/sale_form.html', {'plan': plan})


@login_required
def print_receipt_view(request, sale_id):
    sale = get_object_or_404(Sale.objects.select_related('customer').prefetch_related('items__product'), pk=sale_id)
    return render(request, 'sales/receipt.html', {'sale': sale})


@login_required
def print_receipt_full(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related('customer', 'installment_plan')
        .prefetch_related('items__product', 'installment_plan__payments'),
        pk=sale_id
    )
    
    # Get payment history for installments
    payments = []
    if hasattr(sale, 'installment_plan'):
        payments = sale.installment_plan.payments.all().order_by('payment_date')
    
    # Three copies: Office Copy, Customer Copy, Accounts Copy
    copy_labels = ['Office Copy', 'Customer Copy', 'Accounts Copy']
    
    return render(request, 'sales/receipt_print.html', {
        'sale': sale,
        'payments': payments,
        'copy_labels': copy_labels,
    })


@login_required
def misc_charge_list(request):
    qs = MiscCharge.objects.order_by('-date', '-created_at')
    # simple filter by category
    category = request.GET.get('category')
    if category:
        qs = qs.filter(category=category)
    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'sales/misc_charge_list.html', {'page_obj': page_obj, 'category': category})


@login_required
def misc_charge_create(request):
    # allow preselecting category via GET param ?category=TRANSPORT or SALARY
    pre_category = request.GET.get('category')
    from django.utils import timezone as _tz
    today = _tz.now().date()

    if request.method == 'POST':
        category = request.POST.get('category')
        amount = request.POST.get('amount')
        date = request.POST.get('date')
        description = request.POST.get('description', '')
        try:
            amount_dec = Decimal(amount)
        except Exception:
            messages.error(request, 'Invalid amount provided.')
            return redirect('sales:misc_charge_create')
        mc = MiscCharge.objects.create(
            category=category,
            amount=amount_dec,
            date=date,
            description=description,
            created_by=request.user,
        )
        messages.success(request, f'Misc charge recorded: {mc.get_category_display()} Rs {mc.amount}')
        return redirect('sales:misc_charge_list')
    return render(request, 'sales/misc_charge_form.html', {'category': pre_category, 'today': today})


@login_required
def ledger_view(request):
    """General ledger combining sales (debits) and installment payments (credits).
    Shows running balance. Optional filters: customer, start_date, end_date, payment_type.
    Balance interpretation: Each sale increases (debit) the receivable balance; each installment payment decreases it.
    """
    customer_id = request.GET.get('customer')
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    payment_type = request.GET.get('payment_type')  # FULL or INSTALLMENT

    entries = []

    sales_qs = Sale.objects.select_related('customer').order_by('date')
    if customer_id:
        sales_qs = sales_qs.filter(customer_id=customer_id)
    if payment_type in ('FULL', 'INSTALLMENT'):
        sales_qs = sales_qs.filter(payment_type=payment_type)
    if start_date:
        try:
            dt_start = datetime.strptime(start_date, '%Y-%m-%d')
            sales_qs = sales_qs.filter(date__gte=dt_start)
        except ValueError:
            pass
    if end_date:
        try:
            dt_end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            sales_qs = sales_qs.filter(date__lt=dt_end)
        except ValueError:
            pass

    for s in sales_qs:
        entries.append({
            'date': s.date,
            'type': 'SALE',
            'ref': s.id,
            'customer': s.customer.name,
            'description': f"Sale #{s.id} ({s.get_payment_type_display()})",
            'debit': s.total_amount,
            'credit': Decimal('0'),
        })

    pay_qs = InstallmentPayment.objects.select_related('plan__sale__customer', 'plan').order_by('payment_date')
    if customer_id:
        pay_qs = pay_qs.filter(plan__sale__customer_id=customer_id)
    if start_date:
        try:
            dt_start = datetime.strptime(start_date, '%Y-%m-%d')
            pay_qs = pay_qs.filter(payment_date__gte=dt_start.date())
        except ValueError:
            pass
    if end_date:
        try:
            dt_end = datetime.strptime(end_date, '%Y-%m-%d')
            pay_qs = pay_qs.filter(payment_date__lte=dt_end.date())
        except ValueError:
            pass

    # Payments only relevant for installment sales; optionally filter by payment_type INSTALLMENT
    if payment_type == 'INSTALLMENT':
        pay_qs = pay_qs.filter(plan__sale__payment_type='INSTALLMENT')

    for p in pay_qs:
        entries.append({
            'date': datetime.combine(p.payment_date, datetime.min.time()).replace(tzinfo=timezone.get_current_timezone()),
            'type': 'PAYMENT',
            'ref': p.plan.sale.id,
            'customer': p.plan.sale.customer.name,
            'description': f"Installment Payment (Sale #{p.plan.sale.id})",
            'debit': Decimal('0'),
            'credit': p.amount_paid,
        })

    # Sort all entries by date ascending then type (SALE before PAYMENT if same timestamp for clarity)
    entries.sort(key=lambda e: (e['date'], 0 if e['type'] == 'SALE' else 1))

    running_balance = Decimal('0')
    for e in entries:
        running_balance += e['debit']
        running_balance -= e['credit']
        e['balance'] = running_balance

    # Simple pagination for potentially large ledgers
    page_obj = Paginator(entries, 25).get_page(request.GET.get('page'))

    # Customers list for filter dropdown
    from customers.models import Customer
    customers = Customer.objects.all().order_by('name')

    return render(request, 'sales/ledger.html', {
        'page_obj': page_obj,
        'customers': customers,
        'customer_id': customer_id,
        'start_date': start_date,
        'end_date': end_date,
        'payment_type': payment_type,
        'running_final': running_balance,
    })


@login_required
def balance_sheet_view(request):
    # Delegate to helper and render
    data = _compute_balance_sheet()
    return render(request, 'sales/balance_sheet.html', data)


def _compute_balance_sheet():
    """Compute balance sheet values and return a dict for templates/exports."""
    # Inventory value = sum(purchasing_price * stock_quantity)
    inv_expr = ExpressionWrapper(F('purchasing_price') * F('stock_quantity'), output_field=DecimalField(max_digits=18, decimal_places=2))
    inventory_value = Product.objects.aggregate(s=Sum(inv_expr))['s'] or Decimal('0')

    # Cash: sum of FULL sales + all installment payments received
    cash_full_sales = Sale.objects.filter(payment_type='FULL').aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    cash_installments = InstallmentPayment.objects.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
    cash_on_hand = (cash_full_sales or Decimal('0')) + (cash_installments or Decimal('0'))

    # Accounts receivable: outstanding from installment plans
    plans = InstallmentPlan.objects.all().annotate(paid=Sum('payments__amount_paid'))
    accounts_receivable = Decimal('0')
    for p in plans:
        total_due = p.sale.total_amount
        paid = p.paid or Decimal('0')
        diff = total_due - paid
        if diff > 0:
            accounts_receivable += diff

    total_assets = cash_on_hand + accounts_receivable + inventory_value

    # Liabilities - not tracked in this system; show 0 for now
    total_liabilities = Decimal('0')

    # Equity (basic): Assets - Liabilities
    equity = total_assets - total_liabilities

    return {
        'inventory_value': inventory_value,
        'cash_on_hand': cash_on_hand,
        'accounts_receivable': accounts_receivable,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'equity': equity,
    }


@login_required
def balance_sheet_export(request):
    """Export balance sheet in CSV or Excel (HTML) format. Use ?format=csv or ?format=xls or ?format=print (redirect to printable view)."""
    fmt = request.GET.get('format', 'csv').lower()
    data = _compute_balance_sheet()

    now = datetime.now().strftime('%Y%m%d_%H%M%S')

    if fmt == 'print' or fmt == 'pdf':
        # For PDF we provide the printable HTML view — users can print/save as PDF from browser.
        return redirect(reverse('sales:balance_sheet_print'))

    if fmt == 'xls':
        # Return a simple HTML table that Excel can open
        filename = f'balance_sheet_{now}.xls'
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        # Build a minimal HTML table
        html = ['<table border="1">']
        html.append('<tr><th>Line</th><th>Amount (Rs)</th></tr>')
        html.append(f'<tr><td>Cash on Hand</td><td>{data["cash_on_hand"]}</td></tr>')
        html.append(f'<tr><td>Accounts Receivable</td><td>{data["accounts_receivable"]}</td></tr>')
        html.append(f'<tr><td>Inventory Value</td><td>{data["inventory_value"]}</td></tr>')
        html.append(f'<tr><td></td><td></td></tr>')
        html.append(f'<tr><td><strong>Total Assets</strong></td><td><strong>{data["total_assets"]}</strong></td></tr>')
        html.append(f'<tr><td>Total Liabilities</td><td>{data["total_liabilities"]}</td></tr>')
        html.append(f'<tr><td><strong>Equity</strong></td><td><strong>{data["equity"]}</strong></td></tr>')
        html.append('</table>')
        response.write(''.join(html))
        return response

    # Default: CSV
    filename = f'balance_sheet_{now}.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['Line', 'Amount (Rs)'])
    writer.writerow(['Cash on Hand', str(data['cash_on_hand'])])
    writer.writerow(['Accounts Receivable', str(data['accounts_receivable'])])
    writer.writerow(['Inventory Value', str(data['inventory_value'])])
    writer.writerow([])
    writer.writerow(['Total Assets', str(data['total_assets'])])
    writer.writerow(['Total Liabilities', str(data['total_liabilities'])])
    writer.writerow(['Equity', str(data['equity'])])
    return response


@login_required
def balance_sheet_print(request):
    """Printable balance sheet HTML page - includes a small print button to save as PDF from browser."""
    data = _compute_balance_sheet()
    return render(request, 'sales/balance_sheet_print.html', data)
