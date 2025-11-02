from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Product


class CartTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='u', password='p')
        self.product = Product.objects.create(name='Item', price=Decimal('10.00'), stock_quantity=5)

    def test_add_and_remove_cart(self):
        self.client.login(username='u', password='p')
        # add to cart
        resp = self.client.post(reverse('products:add_to_cart', args=[self.product.id]), {'quantity': 2})
        self.assertEqual(resp.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product.id), cart)
        self.assertEqual(cart[str(self.product.id)]['quantity'], 2)

        # update cart to zero -> removes
        resp = self.client.post(reverse('products:update_cart'), {f'qty_{self.product.id}': '0'})
        self.assertEqual(resp.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product.id), cart)
