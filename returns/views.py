from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import CustomerReturn, VendorReturn, ReturnItem
from .forms import CustomerReturnForm, VendorReturnForm, ReturnItemForm
from products.models import Product
from customers.models import Customer
from vendor.models import Vendor
from sales.models import Sale
from vendor.models import Purchase


@login_required
def customer_return_create(request):
    products = Product.objects.all().order_by('name')
    customers = Customer.objects.all().order_by('name')
    form_errors = []
    prefill_items = None
    prefill_customer = None
    # support prefill from a sale: ?from_sale=<sale_id>
    if request.method == 'GET' and request.GET.get('from_sale'):
        try:
            s = Sale.objects.prefetch_related('items__product').get(pk=request.GET.get('from_sale'))
            prefill_customer = s.customer.id
            prefill_items = []
            for it in s.items.all():
                prefill_items.append({
                    'product_id': it.product.id,
                    'quantity': it.quantity,
                    'unit_cost': it.unit_price,
                    'subtotal': it.unit_price * it.quantity,
                })
        except Sale.DoesNotExist:
            pass
    if request.method == 'POST':
        header_form = CustomerReturnForm(request.POST)
        # build item forms from posted lists
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        unit_costs = request.POST.getlist('unit_cost')

        item_forms = []
        if not product_ids:
            form_errors.append('Add at least one return item')
        for i, pid in enumerate(product_ids):
            data = {
                'product': pid,
                'quantity': quantities[i] if i < len(quantities) else '0',
                'unit_cost': unit_costs[i] if i < len(unit_costs) else '0',
            }
            f = ReturnItemForm(data)
            item_forms.append(f)
            if not f.is_valid():
                form_errors.append(f'Item {i+1}: ' + '; '.join([f'{k}: {v[0]}' for k, v in f.errors.items()]))

        if not header_form.is_valid():
            form_errors.append('Customer selection is required')

        if form_errors:
            # re-render with errors
            return render(request, 'returns/customer_return_form.html', {'products': products, 'customers': customers, 'form_errors': form_errors, 'prefill_items': prefill_items, 'prefill_customer': prefill_customer})

        # all valid -> create return
        customer = header_form.cleaned_data['customer']
        cret = CustomerReturn.objects.create(created_by=request.user, customer=customer, notes=header_form.cleaned_data.get('notes', ''))
        total = Decimal('0')
        for f in item_forms:
            cd = f.cleaned_data
            product = cd['product']
            qty = cd['quantity']
            unit_cost = cd['unit_cost']
            subtotal = unit_cost * qty
            ReturnItem.objects.create(customer_return=cret, product=product, quantity=qty, unit_cost=unit_cost, subtotal=subtotal)
            total += subtotal
            # increase stock for customer returns
            product.stock_quantity = (product.stock_quantity or 0) + qty
            product.save()

        cret.total_amount = total
        cret.save()
        messages.success(request, f'Customer return recorded (#{cret.id})')
        return redirect('returns:customer_return_detail', pk=cret.id)

    return render(request, 'returns/customer_return_form.html', {'products': products, 'customers': customers, 'prefill_items': prefill_items, 'prefill_customer': prefill_customer})


@login_required
def vendor_return_create(request):
    products = Product.objects.all().order_by('name')
    vendors = Vendor.objects.all().order_by('name')
    form_errors = []
    prefill_items = None
    prefill_vendor = None
    # support prefill from a purchase: ?from_purchase=<purchase_id>
    if request.method == 'GET' and request.GET.get('from_purchase'):
        try:
            p = Purchase.objects.prefetch_related('items__product').get(pk=request.GET.get('from_purchase'))
            prefill_vendor = p.vendor.id
            prefill_items = []
            for it in p.items.all():
                prefill_items.append({
                    'product_id': it.product.id,
                    'quantity': it.quantity,
                    'unit_cost': it.unit_cost,
                    'subtotal': it.unit_cost * it.quantity,
                })
        except Purchase.DoesNotExist:
            pass
    if request.method == 'POST':
        header_form = VendorReturnForm(request.POST)
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        unit_costs = request.POST.getlist('unit_cost')

        item_forms = []
        if not product_ids:
            form_errors.append('Add at least one return item')
        for i, pid in enumerate(product_ids):
            data = {
                'product': pid,
                'quantity': quantities[i] if i < len(quantities) else '0',
                'unit_cost': unit_costs[i] if i < len(unit_costs) else '0',
            }
            f = ReturnItemForm(data)
            item_forms.append(f)
            if not f.is_valid():
                form_errors.append(f'Item {i+1}: ' + '; '.join([f'{k}: {v[0]}' for k, v in f.errors.items()]))

        if not header_form.is_valid():
            form_errors.append('Vendor selection is required')

        if form_errors:
            return render(request, 'returns/vendor_return_form.html', {'products': products, 'vendors': vendors, 'form_errors': form_errors, 'prefill_items': prefill_items, 'prefill_vendor': prefill_vendor})

        vendor_obj = header_form.cleaned_data['vendor']
        vret = VendorReturn.objects.create(created_by=request.user, vendor=vendor_obj, notes=header_form.cleaned_data.get('notes', ''))
        total = Decimal('0')
        for f in item_forms:
            cd = f.cleaned_data
            product = cd['product']
            qty = cd['quantity']
            unit_cost = cd['unit_cost']
            subtotal = unit_cost * qty
            ReturnItem.objects.create(vendor_return=vret, product=product, quantity=qty, unit_cost=unit_cost, subtotal=subtotal)
            total += subtotal
            # decrease stock for vendor returns, prevent negative
            new_qty = (product.stock_quantity or 0) - qty
            product.stock_quantity = max(0, new_qty)
            product.save()

        vret.total_amount = total
        vret.save()
        messages.success(request, f'Vendor return recorded (#{vret.id})')
        return redirect('returns:vendor_return_detail', pk=vret.id)

    return render(request, 'returns/vendor_return_form.html', {'products': products, 'vendors': vendors, 'prefill_items': prefill_items, 'prefill_vendor': prefill_vendor})


@login_required
def customer_return_detail(request, pk):
    cret = get_object_or_404(CustomerReturn.objects.prefetch_related('items__product'), pk=pk)
    return render(request, 'returns/customer_return_detail.html', {'return': cret})


@login_required
def vendor_return_detail(request, pk):
    vret = get_object_or_404(VendorReturn.objects.prefetch_related('items__product'), pk=pk)
    return render(request, 'returns/vendor_return_detail.html', {'return': vret})


@login_required
def customer_return_list(request):
    qs = CustomerReturn.objects.order_by('-date')
    return render(request, 'returns/customer_return_list.html', {'page_obj': qs})


@login_required
def vendor_return_list(request):
    qs = VendorReturn.objects.order_by('-date')
    return render(request, 'returns/vendor_return_list.html', {'page_obj': qs})
