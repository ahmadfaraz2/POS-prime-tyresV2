from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .models import Customer


@login_required
def customer_list(request):
    qs = Customer.objects.order_by('-created_at')
    page_obj = Paginator(qs, 10).get_page(request.GET.get('page'))
    return render(request, 'customers/customer_list.html', {'page_obj': page_obj})


@login_required
def customer_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone') or None
        email = request.POST.get('email') or None
        address = request.POST.get('address', '')
        if not name:
            messages.error(request, 'Name is required.')
        else:
            Customer.objects.create(name=name, phone=phone, email=email, address=address)
            messages.success(request, f'Customer "{name}" created.')
            return redirect('customers:customer_list')
    return render(request, 'customers/customer_form.html')


@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.name = request.POST.get('name') or customer.name
        customer.phone = request.POST.get('phone') or None
        customer.email = request.POST.get('email') or None
        customer.address = request.POST.get('address', '')
        customer.save()
        messages.success(request, f'Customer "{customer.name}" updated.')
        return redirect('customers:customer_list')
    return render(request, 'customers/customer_form.html', {'customer': customer})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Customer "{name}" deleted.')
        return redirect('customers:customer_list')
    return render(request, 'customers/customer_confirm_delete.html', {'customer': customer})
