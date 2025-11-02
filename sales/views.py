from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator

from .models import Sale, InstallmentPlan, InstallmentPayment


@login_required
def sale_list(request):
    qs = Sale.objects.select_related('customer').order_by('-date')
    page_obj = Paginator(qs, 10).get_page(request.GET.get('page'))
    return render(request, 'sales/sale_list.html', {'page_obj': page_obj})


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
