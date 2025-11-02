from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.db import transaction
from django.shortcuts import get_object_or_404

from products.models import Product
from customers.models import Customer
from .models import Sale, SaleItem, InstallmentPlan


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
            if not installment_data:
                raise ValueError('Installment data is required for installment payments')
            total_installments = int(installment_data.get('total_installments') or 1)
            first_due_date_str = installment_data.get('first_due_date')
            first_due_date = date.fromisoformat(first_due_date_str) if first_due_date_str else date.today()
            
            # Calculate base installment amount (floored to 2 decimals)
            base_amount = (sale.total_amount / Decimal(total_installments)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # The installment_amount stored here is the base per-installment amount
            # Any remainder from rounding will be added to the final installment payment manually
            InstallmentPlan.objects.create(
                sale=sale,
                total_installments=total_installments,
                installment_amount=base_amount,
                first_due_date=first_due_date,
            )

        return sale
