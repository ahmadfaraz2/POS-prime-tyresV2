from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator

from .models import Vendor, Purchase, PurchaseItem
from products.models import Product
from django.views.decorators.http import require_POST



@login_required
def vendor_list(request):
    qs = Vendor.objects.all().order_by('name')
    q = request.GET.get('q')
    if q:
        qs = qs.filter(name__icontains=q)
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'vendor/vendor_list.html', {'page_obj': page_obj, 'q': q})


@login_required
def vendor_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        address = request.POST.get('address')
        if not name:
            messages.error(request, 'Vendor name is required')
            return redirect('vendor:vendor_create')
        v = Vendor.objects.create(name=name, phone=phone, email=email, address=address)
        messages.success(request, f'Created vendor {v.name}')
        return redirect('vendor:vendor_list')
    return render(request, 'vendor/vendor_form.html')


@login_required
def purchase_list(request):
    qs = Purchase.objects.select_related('vendor').order_by('-date')
    # optional filters
    product_id = request.GET.get('product')
    vendor_id = request.GET.get('vendor')
    if vendor_id:
        qs = qs.filter(vendor_id=vendor_id)
    if product_id:
        qs = qs.filter(items__product_id=product_id).distinct()
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    # for filter dropdowns
    vendors = Vendor.objects.all().order_by('name')
    products = Product.objects.all().order_by('name')
    return render(request, 'vendor/purchase_list.html', {'page_obj': page_obj, 'vendors': vendors, 'products': products, 'vendor_id': vendor_id, 'product_id': product_id})


@login_required
def purchase_create(request):
    products = Product.objects.all().order_by('name')
    vendors = Vendor.objects.all().order_by('name')
    if request.method == 'POST':
        vendor_id = request.POST.get('vendor')
        is_received = bool(request.POST.get('is_received'))
        # transport cost (optional)
        try:
            transport_cost = Decimal(request.POST.get('transport_cost', '0') or '0')
        except Exception:
            transport_cost = Decimal('0')
        vendor = get_object_or_404(Vendor, pk=vendor_id)

        # Multi-item support: expect arrays product[], quantity[], unit_cost[]
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        unit_costs = request.POST.getlist('unit_cost')

        if not product_ids:
            messages.error(request, 'Add at least one purchase item')
            return redirect('vendor:purchase_create')
        purchase = Purchase.objects.create(vendor=vendor, created_by=request.user, is_received=is_received, transport_cost=transport_cost)
        total = Decimal('0')
        for i, pid in enumerate(product_ids):
            try:
                product = Product.objects.get(pk=pid)
            except Product.DoesNotExist:
                continue
            try:
                qty = int(quantities[i])
            except Exception:
                qty = 0
            try:
                unit_cost = Decimal(unit_costs[i])
            except Exception:
                unit_cost = Decimal('0')
            subtotal = (unit_cost or Decimal('0')) * (qty or 0)
            if qty <= 0:
                continue
            PurchaseItem.objects.create(purchase=purchase, product=product, quantity=qty, unit_cost=unit_cost, subtotal=subtotal)
            total += subtotal

            if is_received:
                # increase product stock and optionally update purchasing_price
                product.stock_quantity = (product.stock_quantity or 0) + qty
                # update purchasing_price to latest cost
                product.purchasing_price = unit_cost
                product.save()

        # include transport cost in final total
        purchase.total_amount = total + (transport_cost or Decimal('0'))
        purchase.save()
        messages.success(request, f'Purchase created (#{purchase.id})')
        return redirect('vendor:purchase_detail', pk=purchase.id)

    return render(request, 'vendor/purchase_form.html', {'products': products, 'vendors': vendors})


@login_required
def purchase_print(request, pk):
    purchase = get_object_or_404(Purchase.objects.select_related('vendor').prefetch_related('items__product'), pk=pk)
    copy_labels = ['Vendor Copy', 'Office Copy', 'Accounting Copy']
    items = list(purchase.items.all())
    items_total = sum((item.subtotal or Decimal('0')) for item in items)
    return render(request, 'vendor/purchase_receipt_print.html', {'purchase': purchase, 'copy_labels': copy_labels, 'items_total': items_total})


@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase.objects.prefetch_related('items__product'), pk=pk)
    items = list(purchase.items.all())
    items_total = sum((item.subtotal or Decimal('0')) for item in items)
    return render(request, 'vendor/purchase_detail.html', {'purchase': purchase, 'items_total': items_total})


@login_required
@require_POST
def purchase_mark_received(request, pk):
    """Mark a purchase as received and update product stock. POST only."""
    purchase = get_object_or_404(Purchase.objects.prefetch_related('items__product'), pk=pk)
    if purchase.is_received:
        messages.info(request, 'This purchase is already marked as received.')
        return redirect('vendor:purchase_detail', pk=pk)

    total_added = 0
    for item in purchase.items.all():
        product = item.product
        # increase stock
        product.stock_quantity = (product.stock_quantity or 0) + item.quantity
        # update purchasing price to latest unit cost
        product.purchasing_price = item.unit_cost
        product.save()
        total_added += item.quantity

    purchase.is_received = True
    purchase.save()
    messages.success(request, f'Purchase marked as received. Stock increased by {total_added} items.')
    return redirect('vendor:purchase_detail', pk=pk)
