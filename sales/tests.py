from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from products.models import Product
from customers.models import Customer
from .utils import create_sale_from_cart
from .models import Sale, SaleItem, InstallmentPlan, InstallmentPayment


class CreateSaleFromCartTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='u', password='p')
        self.customer = Customer.objects.create(name='C')
        self.p1 = Product.objects.create(name='A', price=Decimal('5.00'), stock_quantity=10)
        self.p2 = Product.objects.create(name='B', price=Decimal('2.50'), stock_quantity=3)

    def test_creates_sale_and_reduces_stock(self):
        cart = {
            str(self.p1.id): {'product_id': self.p1.id, 'name': 'A', 'price': Decimal('5.00'), 'quantity': 2, 'subtotal': Decimal('10.00')},
            str(self.p2.id): {'product_id': self.p2.id, 'name': 'B', 'price': Decimal('2.50'), 'quantity': 1, 'subtotal': Decimal('2.50')},
        }
        sale = create_sale_from_cart(self.user, self.customer.id, cart, payment_type='FULL')
        self.assertIsInstance(sale, Sale)
        self.assertEqual(sale.items.count(), 2)
        self.p1.refresh_from_db(); self.p2.refresh_from_db()
        self.assertEqual(self.p1.stock_quantity, 8)
        self.assertEqual(self.p2.stock_quantity, 2)

    def test_insufficient_stock_raises(self):
        cart = {str(self.p2.id): {'product_id': self.p2.id, 'name': 'B', 'price': Decimal('2.50'), 'quantity': 99, 'subtotal': Decimal('247.50')}}
        with self.assertRaises(ValueError):
            create_sale_from_cart(self.user, self.customer.id, cart, payment_type='FULL')


class LedgerViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='pass1234')
        self.client.login(username='tester', password='pass1234')
        self.customer = Customer.objects.create(name='Ali', phone='123')
        self.product = Product.objects.create(name='Tyre', price=Decimal('1000.00'), stock_quantity=50)

    def _create_installment_sale(self, total=Decimal('3000.00')):
        sale = Sale.objects.create(customer=self.customer, created_by=self.user, payment_type='INSTALLMENT', total_amount=total, is_completed=True)
        SaleItem.objects.create(sale=sale, product=self.product, quantity=3, unit_price=Decimal('1000.00'), subtotal=total)
        plan = InstallmentPlan.objects.create(sale=sale, total_installments=3, installment_amount=Decimal('1000.00'), first_due_date=timezone.now().date())
        return sale, plan

    def test_ledger_running_balance(self):
        # Create one full sale and one installment sale with payments
        full_sale = Sale.objects.create(customer=self.customer, created_by=self.user, payment_type='FULL', total_amount=Decimal('2000.00'), is_completed=True)
        SaleItem.objects.create(sale=full_sale, product=self.product, quantity=2, unit_price=Decimal('1000.00'), subtotal=Decimal('2000.00'))

        inst_sale, plan = self._create_installment_sale()
        InstallmentPayment.objects.create(plan=plan, amount_paid=Decimal('1000.00'))
        InstallmentPayment.objects.create(plan=plan, amount_paid=Decimal('500.00'))

        url = reverse('sales:ledger')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        page_obj = resp.context['page_obj']
        balances = [e['balance'] for e in page_obj.object_list]
        # Expect increases and subsequent decreases
        self.assertTrue(any(b > Decimal('0') for b in balances))
        self.assertTrue(any(balances[i] > balances[i+1] for i in range(len(balances)-1)))

    def test_ledger_filters_customer(self):
        other_customer = Customer.objects.create(name='Sara', phone='999')
        Sale.objects.create(customer=self.customer, created_by=self.user, payment_type='FULL', total_amount=Decimal('1000.00'), is_completed=True)
        Sale.objects.create(customer=other_customer, created_by=self.user, payment_type='FULL', total_amount=Decimal('500.00'), is_completed=True)
        url = reverse('sales:ledger') + f'?customer={self.customer.id}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        for e in resp.context['page_obj'].object_list:
            self.assertEqual(e['customer'], 'Ali')
