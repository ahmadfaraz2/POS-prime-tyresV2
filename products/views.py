from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .models import Product
from customers.models import Customer
from sales.utils import create_sale_from_cart
from django.db.models import F, ExpressionWrapper, DecimalField


def _get_cart(request):
    cart = request.session.get('cart', {})
    request.session.setdefault('cart', cart)
    return cart


def _save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


@login_required
def product_list_view(request):
    products_qs = Product.objects.order_by('-created_at')
    q = request.GET.get('q', '').strip()
    if q:
        # Basic icontains across name, brand, type, size
        from django.db.models import Q
        products_qs = products_qs.filter(
            Q(name__icontains=q) |
            Q(brand__icontains=q) |
            Q(type__icontains=q) |
            Q(size__icontains=q)
        )
    # annotate profit per unit and total profit for current stock
    profit_per_expr = ExpressionWrapper(F('price') - F('purchasing_price'), output_field=DecimalField(max_digits=12, decimal_places=2))
    total_profit_expr = ExpressionWrapper((F('price') - F('purchasing_price')) * F('stock_quantity'), output_field=DecimalField(max_digits=14, decimal_places=2))
    products_qs = products_qs.annotate(profit_per=profit_per_expr, total_profit=total_profit_expr)

    paginator = Paginator(products_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'products/product_list.html', {'page_obj': page_obj, 'q': q})


@login_required
def product_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        purchasing_price = request.POST.get('purchasing_price')
        stock_quantity = request.POST.get('stock_quantity')
        brand = request.POST.get('brand')
        size = request.POST.get('size')
        type_ = request.POST.get('type')
        description = request.POST.get('description', '')
        if not name or not price:
            messages.error(request, 'Name and price are required.')
        else:
            product = Product.objects.create(
                name=name,
                price=Decimal(price),
                purchasing_price=Decimal(purchasing_price or '0'),
                stock_quantity=int(stock_quantity or 0),
                brand=brand or None,
                size=size or None,
                type=type_ or None,
                description=description,
            )
            messages.success(request, f'Product "{product.name}" created.')
            return redirect('products:product_list')
    return render(request, 'products/product_form.html')


@login_required
def product_update_view(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.name = request.POST.get('name') or product.name
        price = request.POST.get('price')
        if price:
            product.price = Decimal(price)
        purchasing_price = request.POST.get('purchasing_price')
        if purchasing_price is not None and purchasing_price != '':
            product.purchasing_price = Decimal(purchasing_price)
        stock_quantity = request.POST.get('stock_quantity')
        if stock_quantity is not None and stock_quantity != '':
            product.stock_quantity = int(stock_quantity)
        product.brand = request.POST.get('brand') or None
        product.size = request.POST.get('size') or None
        product.type = request.POST.get('type') or None
        product.description = request.POST.get('description', '')
        product.save()
        messages.success(request, f'Product "{product.name}" updated.')
        return redirect('products:product_list')
    return render(request, 'products/product_form.html', {'product': product})


@login_required
def product_delete_view(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted.')
        return redirect('products:product_list')
    return render(request, 'products/product_confirm_delete.html', {'product': product})


@login_required
def add_to_cart_view(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        qty = int(request.POST.get('quantity', '1'))
    else:
        qty = 1
    if qty <= 0:
        messages.error(request, 'Quantity must be positive.')
        return redirect('products:product_list')

    cart = _get_cart(request)
    key = str(product.id)
    if key in cart:
        cart[key]['quantity'] += qty
    else:
        cart[key] = {
            'product_id': product.id,
            'name': product.name,
            'price': str(product.price),
            'quantity': qty,
            'subtotal': str((Decimal(str(product.price)) * qty).quantize(Decimal('0.01'))),
        }
    # Recompute subtotal (store as string for JSON-serializable session)
    cart[key]['subtotal'] = str((Decimal(cart[key]['price']) * int(cart[key]['quantity'])).quantize(Decimal('0.01')))
    _save_cart(request, cart)
    messages.success(request, f'Added {qty} x {product.name} to cart.')
    return redirect('products:cart_view')


@login_required
def remove_from_cart_view(request, product_id):
    cart = _get_cart(request)
    key = str(product_id)
    if key in cart:
        del cart[key]
        _save_cart(request, cart)
        messages.success(request, 'Item removed from cart.')
    else:
        messages.error(request, 'Item not in cart.')
    return redirect('products:cart_view')


@login_required
def update_cart_view(request):
    if request.method == 'POST':
        cart = _get_cart(request)
        for key, item in list(cart.items()):
            qty_str = request.POST.get(f'qty_{key}', None)
            if qty_str is None:
                continue
            try:
                qty = int(qty_str)
            except ValueError:
                qty = item['quantity']
            if qty <= 0:
                del cart[key]
            else:
                item['quantity'] = qty
                item['subtotal'] = str((Decimal(item['price']) * qty).quantize(Decimal('0.01')))
        _save_cart(request, cart)
        messages.success(request, 'Cart updated.')
    return redirect('products:cart_view')


@login_required
def cart_view(request):
    cart = _get_cart(request)
    total = sum(Decimal(item['subtotal']) for item in cart.values()) if cart else Decimal('0')
    return render(request, 'products/cart.html', {'cart': cart, 'total': total})


@login_required
def checkout_view(request):
    cart = _get_cart(request)
    if not cart:
        messages.error(request, 'Your cart is empty.')
        return redirect('products:cart_view')

    customers = Customer.objects.all().order_by('name')

    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        payment_type = request.POST.get('payment_type')

        # Allow Anonymous option
        if customer_id == 'anonymous' or not customer_id:
            customer, _ = Customer.objects.get_or_create(name='Anonymous')
            customer_id = customer.id

        installment_data = None
        if payment_type == 'INSTALLMENT':
            # New behaviour: accept an optional free-text note for installment
            # plans and an optional initial payment amount to record now.
            note = request.POST.get('installment_note', '').strip()
            initial_payment_str = request.POST.get('initial_payment', '').strip() or '0'
            try:
                initial_payment = Decimal(initial_payment_str)
            except Exception:
                initial_payment = Decimal('0')
            installment_data = {'notes': note, 'initial_payment': str(initial_payment)} if (note or initial_payment > 0) else None

        try:
            sale = create_sale_from_cart(
                user=request.user,
                customer_id=customer_id,
                cart=cart,
                payment_type=payment_type,
                installment_data=installment_data,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('products:checkout')

        # Clear cart
        request.session['cart'] = {}
        request.session.modified = True
        messages.success(request, f'Sale #{sale.id} created successfully.')
        return redirect('sales:receipt', sale_id=sale.id)

    total = sum(Decimal(item['subtotal']) for item in cart.values())
    return render(request, 'products/checkout.html', {
        'cart': cart,
        'total': total,
        'customers': customers,
    })
