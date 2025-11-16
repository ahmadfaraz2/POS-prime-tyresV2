from decimal import Decimal
from django import forms
from .models import CustomerReturn, VendorReturn, ReturnItem
from products.models import Product
from customers.models import Customer
from vendor.models import Vendor


class CustomerReturnForm(forms.Form):
    customer = forms.ModelChoiceField(queryset=Customer.objects.all())
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows':2}))


class VendorReturnForm(forms.Form):
    vendor = forms.ModelChoiceField(queryset=Vendor.objects.all())
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows':2}))


class ReturnItemForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all())
    quantity = forms.IntegerField(min_value=1)
    unit_cost = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)
