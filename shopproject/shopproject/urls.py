from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('customers/', include('customers.urls')),
    path('sales/', include('sales.urls')),
    path('vendor/', include('vendor.urls')),
    path('returns/', include('returns.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('', RedirectView.as_view(pattern_name='dashboard:dashboard_view', permanent=False)),
]
