from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .models import Customer
from sales.models import Sale
from decimal import Decimal
from django.db.models import Sum


@login_required
def customer_list(request):
    qs = Customer.objects.order_by('-created_at')
    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q)
        )
    page_obj = Paginator(qs, 10).get_page(request.GET.get('page'))
    return render(request, 'customers/customer_list.html', {'page_obj': page_obj, 'q': q})


@login_required
def customer_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone') or None
        email = request.POST.get('email') or None
        address = request.POST.get('address', '')
        if not name:
            messages.error(request, 'Name is required.')
        else:
            Customer.objects.create(name=name, phone=phone, email=email, address=address)
            messages.success(request, f'Customer "{name}" created.')
            return redirect('customers:customer_list')
    return render(request, 'customers/customer_form.html')


@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.name = request.POST.get('name') or customer.name
        customer.phone = request.POST.get('phone') or None
        customer.email = request.POST.get('email') or None
        customer.address = request.POST.get('address', '')
        customer.save()
        messages.success(request, f'Customer "{customer.name}" updated.')
        return redirect('customers:customer_list')
    return render(request, 'customers/customer_form.html', {'customer': customer})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Customer "{name}" deleted.')
        return redirect('customers:customer_list')
    return render(request, 'customers/customer_confirm_delete.html', {'customer': customer})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    # All sales for this customer (paginated)
    sales_qs = Sale.objects.filter(customer=customer).select_related('created_by').prefetch_related('items__product', 'installment_plan__payments').order_by('-date')
    page_obj = Paginator(sales_qs, 10).get_page(request.GET.get('page'))

    # Aggregate totals and purchased products
    total_amount = Decimal('0')
    total_paid = Decimal('0')
    purchased = {}

    for s in sales_qs:
        amt = s.total_amount or Decimal('0')
        total_amount += amt
        plan = getattr(s, 'installment_plan', None)
        if plan:
            paid_for_sale = Decimal('0')
            for p in plan.payments.all():
                paid_for_sale += (p.amount_paid or Decimal('0'))
            total_paid += paid_for_sale

        # accumulate products
        for it in s.items.all():
            prod = it.product
            entry = purchased.get(prod.id)
            if not entry:
                entry = {'product': prod, 'quantity': 0, 'spent': Decimal('0')}
                purchased[prod.id] = entry
            entry['quantity'] += it.quantity or 0
            entry['spent'] += it.subtotal or Decimal('0')

    total_remaining = total_amount - total_paid

    # Convert purchased dict to list for template
    purchased_list = [v for k, v in purchased.items()]

    context = {
        'customer': customer,
        'page_obj': page_obj,
        'purchased_list': purchased_list,
        'total_amount': total_amount.quantize(Decimal('0.01')),
        'total_paid': total_paid.quantize(Decimal('0.01')),
        'total_remaining': total_remaining.quantize(Decimal('0.01')),
    }
    return render(request, 'customers/customer_detail.html', context)
