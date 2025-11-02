from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User

from products.models import Product
from customers.models import Customer
from .utils import create_sale_from_cart
from .models import Sale, SaleItem


class CreateSaleFromCartTests(TestCase):
    def setUp(self):
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
