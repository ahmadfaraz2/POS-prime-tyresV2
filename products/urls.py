from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list_view, name='product_list'),
    path('create/', views.product_create_view, name='product_create'),
    path('<int:pk>/edit/', views.product_update_view, name='product_update'),
    path('<int:pk>/delete/', views.product_delete_view, name='product_delete'),

    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/', views.add_to_cart_view, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart_view, name='remove_from_cart'),
    path('cart/update/', views.update_cart_view, name='update_cart'),
    path('checkout/', views.checkout_view, name='checkout'),
]
