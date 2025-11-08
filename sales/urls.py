from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    # path('ledger/', views.ledger_view, name='ledger'),
    path('export/', views.export_sales_csv, name='export_csv'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('installments/', views.installment_list, name='installment_list'),
    path('installments/<int:plan_id>/pay/', views.installment_payment_create, name='installment_payment_create'),
    path('receipt/<int:sale_id>/', views.print_receipt_view, name='receipt'),
    path('receipt/<int:sale_id>/print/', views.print_receipt_full, name='receipt_print'),
]
