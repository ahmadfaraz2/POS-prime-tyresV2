from django.urls import path
from . import views

app_name = 'balancesheet'

urlpatterns = [
    path('', views.balancesheet_view, name='balancesheet_view'),
]
