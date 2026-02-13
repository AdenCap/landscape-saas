from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.forms import EmployeeForm, EmployeeCreateForm, EmployeePasswordForm

User = get_user_model()


def _get_business(request):
    return getattr(request.user, 'business', None)


@role_required("owner")
def employee_list(request):
    """List all employees (users in the owner's business)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to manage employees.")
        return redirect("/")

    employees = User.objects.filter(business=business).order_by('role', 'first_name', 'last_name', 'username')
    return render(request, "accounts/employee_list.html", {"employees": employees})


@role_required("owner")
def employee_add(request):
    """Add a new employee with login credentials."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to add employees.")
        return redirect("/")

    if request.method == "POST":
        form = EmployeeCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.business = business
            user.save()
            messages.success(request, f"Employee '{user.get_full_name() or user.username}' added successfully.")
            return redirect("employee_edit", user_id=user.id)
    else:
        form = EmployeeCreateForm()

    return render(request, "accounts/employee_form.html", {
        "form": form,
        "title": "Add Employee",
        "is_create": True,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def employee_edit(request, user_id):
    """Edit employee profile and optionally change password."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    employee = get_object_or_404(User, id=user_id, business=business)

    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Employee updated.")
            return redirect("employee_edit", user_id=employee.id)
    else:
        form = EmployeeForm(instance=employee)

    return render(request, "accounts/employee_form.html", {
        "form": form,
        "employee": employee,
        "title": "Edit Employee",
        "is_create": False,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def employee_password(request, user_id):
    """Owner can set/reset an employee's password."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    employee = get_object_or_404(User, id=user_id, business=business)

    if request.method == "POST":
        form = EmployeePasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password1"]
            employee.set_password(new_password)
            employee.save()
            messages.success(request, f"Password updated for {employee.get_full_name() or employee.username}.")
            return redirect("employee_edit", user_id=employee.id)
    else:
        form = EmployeePasswordForm()

    return render(request, "accounts/employee_password.html", {
        "form": form,
        "employee": employee,
    })
