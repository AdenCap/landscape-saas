from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import LoginView as AuthLoginView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.ratelimit import ratelimit
from accounts.utils import get_business as _get_business
from django.utils import timezone as tz
from accounts.forms import (
    EmployeeForm,
    EmployeeCreateForm,
    EmployeePasswordForm,
    EmployeePaymentForm,
    SignUpForm,
    SendNotificationForm,
)
from accounts.models import EmployeePayment, Notification
from businesses.models import Business
from jobs.models import Crew

User = get_user_model()


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch")
class LoginView(AuthLoginView):
    """After password login, always send to post-login check (2FA on new device); preserve next."""

    def get_success_url(self):
        # Always go through post-login check; pass through intended destination
        base = settings.LOGIN_REDIRECT_URL
        redirect_to = self.get_redirect_url()  # already validates safe URL
        if redirect_to:
            return base + "?" + urlencode({self.redirect_field_name: redirect_to})
        return base


@require_http_methods(["GET", "POST"])
def signup(request):
    """Public signup: create a business and an owner user, then log them in."""
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            business_name = form.cleaned_data.pop("business_name")
            business = Business.objects.create(name=business_name)
            user = form.save(commit=False)
            user.business = business
            user.role = "owner"
            user.save()
            login(request, user)
            messages.success(request, f"Welcome! Your business '{business.name}' is set up.")
            return redirect("/")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


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

    payments = EmployeePayment.objects.filter(employee=employee).order_by("-paid_date", "-created_at")
    total_paid = sum(p.amount for p in payments)
    default_paid_date = tz.localdate().isoformat()

    return render(request, "accounts/employee_form.html", {
        "form": form,
        "employee": employee,
        "title": "Edit Employee",
        "is_create": False,
        "payments": payments,
        "total_paid": total_paid,
        "default_paid_date": default_paid_date,
    })


@role_required("owner")
@require_http_methods(["GET", "POST"])
def employee_delete(request, user_id):
    """
    Delete an employee.
    
    Prevents deleting the owner. Related data (jobs, time entries, etc.) will be
    handled according to their on_delete settings (SET_NULL or CASCADE).
    """
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")

    employee = get_object_or_404(User, id=user_id, business=business)

    # Prevent deleting the owner
    if employee.role == "owner":
        messages.error(request, "Cannot delete the business owner. Transfer ownership first or contact support.")
        return redirect("employee_edit", user_id=employee.id)

    # Prevent deleting yourself
    if employee.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect("employee_edit", user_id=employee.id)

    if request.method == "POST":
        # Confirm deletion
        employee_name = employee.get_full_name() or employee.username
        
        # Count related records for warning
        from jobs.models import Job
        from time_tracking.models import TimeEntry
        
        job_count = Job.objects.filter(assigned_to=employee).count()
        time_entry_count = TimeEntry.objects.filter(user=employee).count()
        
        # Delete the employee
        # Related data will be handled by on_delete settings:
        # - Jobs: SET_NULL (assigned_to becomes NULL)
        # - Time entries: CASCADE (deleted)
        # - Payments: CASCADE (deleted)
        # - Notifications: CASCADE (deleted)
        employee.delete()
        
        messages.success(request, f"Employee '{employee_name}' has been deleted.")
        
        # Show warning if there was related data
        if job_count > 0 or time_entry_count > 0:
            warnings = []
            if job_count > 0:
                warnings.append(f"{job_count} job assignment(s)")
            if time_entry_count > 0:
                warnings.append(f"{time_entry_count} time entry/entries")
            if warnings:
                messages.info(request, f"Note: {', '.join(warnings)} associated with this employee have been removed or unassigned.")
        
        return redirect("employee_list")
    
    # GET: Show confirmation page
    from jobs.models import Job
    from time_tracking.models import TimeEntry
    
    job_count = Job.objects.filter(assigned_to=employee).count()
    time_entry_count = TimeEntry.objects.filter(user=employee).count()
    payment_count = EmployeePayment.objects.filter(employee=employee).count()
    
    return render(request, "accounts/employee_delete_confirm.html", {
        "employee": employee,
        "job_count": job_count,
        "time_entry_count": time_entry_count,
        "payment_count": payment_count,
    })


@role_required("owner")
@require_POST
def employee_record_payment(request, user_id):
    """Record a payment made to an employee. Redirects back to employee edit."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    employee = get_object_or_404(User, id=user_id, business=business)
    form = EmployeePaymentForm(request.POST)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.employee = employee
        payment.business = business
        payment.save()
        messages.success(request, f"Recorded payment of ${payment.amount} for {payment.paid_date}.")
    else:
        messages.error(request, "Invalid payment details. Check amount and date.")
    return redirect("employee_edit", user_id=employee.id)


@role_required("owner")
@require_http_methods(["GET", "POST"])
def notification_send(request):
    """Owner: send a notification to selected employees and/or crews (multi-select)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    if request.method == "POST":
        form = SendNotificationForm(request.POST, business=business)
        if form.is_valid():
            message = form.cleaned_data["message"].strip()
            if not message:
                messages.error(request, "Please enter a message.")
            else:
                recipient_ids = set()
                if form.cleaned_data.get("send_to_all"):
                    recipient_ids.update(
                        User.objects.filter(business=business)
                        .exclude(pk=request.user.pk)
                        .values_list("pk", flat=True)
                    )
                else:
                    emp_ids = [int(x) for x in (form.cleaned_data.get("employees") or [])]
                    crew_ids = [int(x) for x in (form.cleaned_data.get("crews") or [])]
                    if emp_ids:
                        recipient_ids.update(
                            User.objects.filter(business=business, id__in=emp_ids).values_list("pk", flat=True)
                        )
                    if crew_ids:
                        for crew in Crew.objects.filter(business=business, id__in=crew_ids).prefetch_related("members"):
                            recipient_ids.update(crew.members.values_list("pk", flat=True))
                recipient_ids.discard(request.user.pk)
                created = 0
                for to_user_id in recipient_ids:
                    Notification.objects.create(
                        business=business,
                        from_user=request.user,
                        to_user_id=to_user_id,
                        message=message,
                    )
                    created += 1
                if created:
                    messages.success(request, f"Notification sent to {created} employee(s).")
                else:
                    messages.warning(request, "No recipients found.")
                return redirect("notification_send")
    else:
        form = SendNotificationForm(business=business)
    return render(request, "accounts/notification_send.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def notification_inbox(request):
    """Employees (and owner) see notifications sent to them."""
    notifications = (
        Notification.objects.filter(to_user=request.user)
        .select_related("from_user")
        .order_by("-created_at")[:100]
    )
    unread_count = Notification.objects.filter(to_user=request.user, read_at__isnull=True).count()
    return render(request, "accounts/notification_inbox.html", {
        "notifications": notifications,
        "unread_count": unread_count,
    })


@login_required
@require_http_methods(["POST"])
def notification_mark_read(request, notification_id):
    """Mark a notification as read (only the recipient)."""
    notification = get_object_or_404(Notification, id=notification_id, to_user=request.user)
    if not notification.read_at:
        from django.utils import timezone as tz
        notification.read_at = tz.now()
        notification.save(update_fields=["read_at"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accepts("application/json"):
        from django.http import JsonResponse
        return JsonResponse({"ok": True})
    return redirect("notification_inbox")


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
