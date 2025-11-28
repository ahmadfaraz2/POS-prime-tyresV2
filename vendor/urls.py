from django.urls import path
from . import views

app_name = 'vendor'

urlpatterns = [
    path('', views.vendor_list, name='vendor_list'),
    path('add/', views.vendor_create, name='vendor_create'),
    path('<int:pk>/', views.vendor_detail, name='vendor_detail'),
    path('purchases/', views.purchase_list, name='purchase_list'),
    path('purchases/add/', views.purchase_create, name='purchase_create'),
    path('purchases/<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('purchases/<int:pk>/print/', views.purchase_print, name='purchase_print'),
    path('purchases/<int:pk>/receive/', views.purchase_mark_received, name='purchase_receive'),
    path('purchases/<int:pk>/revoke/', views.purchase_revoke, name='purchase_revoke'),
    path('purchases/<int:pk>/whatsapp/', views.purchase_send_whatsapp, name='purchase_whatsapp'),
    path('purchases/<int:pk>/print/pdf/', views.purchase_print_pdf, name='purchase_print_pdf'),
]
