from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator

from .models import Vendor, Purchase, PurchaseItem
from products.models import Product
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse
from urllib.parse import quote_plus
from django.template.loader import render_to_string
from django.http import HttpResponse
import io
try:
    from xhtml2pdf import pisa
except Exception:
    pisa = None


def _normalize_phone_for_storage(phone: str) -> str:
    """Return sanitized phone digits for storage/wa.me usage.

    - Removes all non-digit characters.
    - If number starts with a single leading '0', convert to Pakistan country code '92'.
    - If empty after stripping, return empty string.
    """
    if not phone:
        return ''
    digits = ''.join(ch for ch in phone if ch.isdigit())
    if not digits:
        return ''
    # Convert local Pakistan leading 0 -> 92 (e.g., 03001234567 -> 923001234567)
    if digits.startswith('0'):
        # Avoid double-conversion if user already entered country code like 0092
        # If the number starts with 00 (international dialing prefix), leave as-is
        if digits.startswith('00'):
            # strip leading zeros but keep rest (e.g., 00923... -> 923...)
            digits = digits.lstrip('0')
        else:
            digits = '92' + digits.lstrip('0')
    return digits




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
        phone_raw = request.POST.get('phone')
        phone = _normalize_phone_for_storage(phone_raw)
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
def purchase_print_pdf(request, pk):
    """Return the purchase receipt as a PDF file using xhtml2pdf."""
    purchase = get_object_or_404(Purchase.objects.select_related('vendor').prefetch_related('items__product'), pk=pk)
    items = list(purchase.items.all())
    items_total = sum((item.subtotal or Decimal('0')) for item in items)
    context = {'purchase': purchase, 'copy_labels': ['Vendor Copy'], 'items_total': items_total}
    html = render_to_string('vendor/purchase_receipt_print.html', context)

    if pisa is None:
        messages.error(request, 'PDF generation is not available (missing xhtml2pdf).')
        return redirect('vendor:purchase_print', pk=pk)

    result = io.BytesIO()
    # Create PDF
    pdf_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result)
    if pdf_status.err:
        messages.error(request, 'Error generating PDF')
        return redirect('vendor:purchase_print', pk=pk)

    result.seek(0)
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    filename = f"purchase_{purchase.id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def purchase_send_whatsapp(request, pk):
    """Redirect to WhatsApp Web with a prefilled message containing the absolute receipt URL."""
    purchase = get_object_or_404(Purchase.objects.select_related('vendor').prefetch_related('items__product'), pk=pk)
    # Build absolute URL to the PDF receipt
    receipt_path = reverse('vendor:purchase_print_pdf', args=[purchase.id])
    absolute_receipt_url = request.build_absolute_uri(receipt_path)
    message = f"Purchase Receipt #{purchase.id} - {absolute_receipt_url}"
    # If vendor has a phone number, attempt to send directly to that number using wa.me/<number>?text=...
    phone = (purchase.vendor.phone or '').strip()
    digits = ''.join(ch for ch in phone if ch.isdigit())
    if digits:
        # If number starts with '0' we avoid guessing country code — fall back to generic share
        if digits.startswith('0'):
            wa_link = f"https://wa.me/?text={quote_plus(message)}"
        else:
            wa_link = f"https://wa.me/{digits}?text={quote_plus(message)}"
    else:
        wa_link = f"https://wa.me/?text={quote_plus(message)}"
    return redirect(wa_link)


@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase.objects.prefetch_related('items__product'), pk=pk)
    items = list(purchase.items.all())
    items_total = sum((item.subtotal or Decimal('0')) for item in items)
    return render(request, 'vendor/purchase_detail.html', {'purchase': purchase, 'items_total': items_total})


@login_required
def vendor_detail(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)

    # All purchases for this vendor (paginated)
    purchases_qs = Purchase.objects.filter(vendor=vendor).select_related('created_by').prefetch_related('items__product').order_by('-date')
    page_obj = Paginator(purchases_qs, 10).get_page(request.GET.get('page'))

    # Aggregate totals and purchased products
    total_amount = Decimal('0')
    total_received = Decimal('0')
    purchased = {}

    for p in purchases_qs:
        amt = p.total_amount or Decimal('0')
        total_amount += amt
        if p.is_received:
            total_received += amt

        for it in p.items.all():
            prod = it.product
            entry = purchased.get(prod.id)
            if not entry:
                entry = {'product': prod, 'quantity': 0, 'spent': Decimal('0')}
                purchased[prod.id] = entry
            entry['quantity'] += it.quantity or 0
            entry['spent'] += it.subtotal or Decimal('0')

    total_unreceived = total_amount - total_received

    purchased_list = [v for k, v in purchased.items()]

    context = {
        'vendor': vendor,
        'page_obj': page_obj,
        'purchased_list': purchased_list,
        'total_amount': total_amount.quantize(Decimal('0.01')),
        'total_received': total_received.quantize(Decimal('0.01')),
        'total_unreceived': total_unreceived.quantize(Decimal('0.01')),
    }
    return render(request, 'vendor/vendor_detail.html', context)


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


@login_required
@require_POST
def purchase_revoke(request, pk):
    """Revoke a previously received purchase: attempt to decrement product stock and unset is_received."""
    purchase = get_object_or_404(Purchase.objects.prefetch_related('items__product'), pk=pk)
    if not purchase.is_received:
        messages.info(request, 'This purchase is not marked as received.')
        return redirect('vendor:purchase_detail', pk=pk)

    # Validate availability first under a transaction to avoid race conditions
    with transaction.atomic():
        # First pass: lock product rows and verify stock sufficiency
        for item in purchase.items.select_related('product').all():
            product = Product.objects.select_for_update().get(pk=item.product_id)
            current_stock = product.stock_quantity or 0
            if current_stock < item.quantity:
                messages.error(request, f"Cannot revoke: product '{product.name}' stock ({current_stock}) is less than quantity to remove ({item.quantity}).")
                return redirect('vendor:purchase_detail', pk=pk)

        # Second pass: decrement stock now that checks passed
        total_removed = 0
        for item in purchase.items.select_related('product').all():
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock_quantity = (product.stock_quantity or 0) - item.quantity
            product.save()
            total_removed += item.quantity

        purchase.is_received = False
        purchase.save()

    messages.success(request, f'Received status revoked. Stock decreased by {total_removed} items.')
    return redirect('vendor:purchase_detail', pk=pk)
