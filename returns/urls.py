from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    path('customer/add/', views.customer_return_create, name='customer_return_create'),
    path('customer/<int:pk>/', views.customer_return_detail, name='customer_return_detail'),
    path('customer/', views.customer_return_list, name='customer_return_list'),

    path('vendor/add/', views.vendor_return_create, name='vendor_return_create'),
    path('vendor/<int:pk>/', views.vendor_return_detail, name='vendor_return_detail'),
    path('vendor/', views.vendor_return_list, name='vendor_return_list'),
]
