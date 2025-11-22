from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.db import transaction
from django.shortcuts import get_object_or_404

from products.models import Product
from customers.models import Customer
from .models import Sale, SaleItem, InstallmentPlan, InstallmentPayment
from django.db.models import Sum


def create_sale_from_cart(user, customer_id, cart, payment_type, installment_data=None):
    if not cart or not len(cart):
        raise ValueError('Cart is empty')

    with transaction.atomic():
        total = sum(Decimal(str(item['subtotal'])) for item in cart.values())
        customer = get_object_or_404(Customer, pk=customer_id)
        sale = Sale.objects.create(
            customer=customer,
            created_by=user,
            payment_type=payment_type,
            total_amount=total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            is_completed=True,
        )

        # lock and decrement stock, create items
        for item in cart.values():
            product = Product.objects.select_for_update().get(pk=item['product_id'])
            qty = int(item['quantity'])
            if product.stock_quantity < qty:
                raise ValueError(f'Insufficient stock for {product.name}')
            unit_price = Decimal(str(item['price']))
            subtotal = (unit_price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=qty,
                unit_price=unit_price,
                subtotal=subtotal,
            )
            product.stock_quantity = product.stock_quantity - qty
            product.save(update_fields=['stock_quantity'])

        if payment_type == 'INSTALLMENT':
            # New behaviour: create a simple InstallmentPlan record which will
            # act as a grouping for ad-hoc `InstallmentPayment` entries. Do not
            # pre-create scheduled payment rows.
            notes = ''
            if installment_data:
                notes = installment_data.get('notes', '')
            plan = InstallmentPlan.objects.create(
                sale=sale,
                notes=notes,
            )

            # If an initial payment was provided at checkout, record it now.
            if installment_data:
                init_amt = installment_data.get('initial_payment')
                try:
                    init_amt_dec = Decimal(str(init_amt)) if init_amt is not None else Decimal('0')
                except Exception:
                    init_amt_dec = Decimal('0')
                if init_amt_dec and init_amt_dec > 0:
                    InstallmentPayment.objects.create(plan=plan, amount_paid=init_amt_dec)
                    # If the initial payment covers the full sale amount, mark plan PAID
                    total_paid = plan.payments.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0')
                    if total_paid >= sale.total_amount:
                        plan.status = 'PAID'
                        plan.save(update_fields=['status'])

        return sale
