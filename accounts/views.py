import json
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import LoginView as AuthLoginView
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import role_required
from accounts.ratelimit import ratelimit, _get_client_ip
from accounts.utils import get_business as _get_business
from django.utils import timezone as tz
from accounts.forms import (
    EmployeeForm,
    EmployeeCreateForm,
    EmployeeInviteForm,
    EmployeePasswordForm,
    EmployeePaymentForm,
    InviteSetPasswordForm,
    SignUpForm,
    SendNotificationForm,
    SocialSignupCompleteForm,
)
from accounts.models import AuditLog, EmployeeInvite, EmployeePayment, Notification
from businesses.models import Business
from jobs.models import Crew

User = get_user_model()
security_logger = logging.getLogger("accounts.security")


# ── Account lockout helpers ──────────────────────────────────────────────
def _lockout_cache_key(username):
    """Cache key for tracking failed login attempts by username."""
    return f"login_lockout:{username.lower()}"


def _is_locked_out(username):
    """Check whether this account is currently locked due to too many failed attempts."""
    data = cache.get(_lockout_cache_key(username))
    if not data:
        return False
    import time
    if data.get("locked_until", 0) > time.time():
        return True
    return False


def _record_failed_attempt(username, ip_address):
    """Record a failed login attempt; lock the account if threshold is exceeded."""
    import time
    key = _lockout_cache_key(username)
    max_attempts = getattr(settings, "MAX_LOGIN_ATTEMPTS", 5)
    window = getattr(settings, "LOGIN_ATTEMPT_WINDOW", 900)
    lockout_duration = getattr(settings, "ACCOUNT_LOCKOUT_DURATION", 900)

    data = cache.get(key) or {"attempts": [], "locked_until": 0}
    now = time.time()
    # Prune old attempts outside the window
    data["attempts"] = [t for t in data["attempts"] if t > now - window]
    data["attempts"].append(now)

    if len(data["attempts"]) >= max_attempts:
        data["locked_until"] = now + lockout_duration
        security_logger.warning(
            "Account locked username=%s ip=%s attempts=%d lockout_seconds=%d",
            username, ip_address, len(data["attempts"]), lockout_duration,
        )

    cache.set(key, data, timeout=max(window, lockout_duration) + 60)


def _clear_failed_attempts(username):
    """Clear failed attempt counter after a successful login."""
    cache.delete(_lockout_cache_key(username))


# ── Audit log helper ────────────────────────────────────────────────────
def _log_auth_event(user, action, ip_address, details=""):
    """Write a login/login_failed event to the AuditLog."""
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            ip_address=ip_address,
            details=details,
        )
    except Exception:
        # Never let audit logging break the login flow
        security_logger.exception("Failed to write audit log for action=%s", action)


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch")
class LoginView(AuthLoginView):
    """
    Secure login view with:
    - IP-based rate limiting (10/min)
    - Account lockout after N failed attempts
    - Audit logging of successes and failures
    - 2FA post-login check
    """

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "").strip()
        ip = _get_client_ip(request)

        # Check lockout before wasting cycles on authentication
        if username and _is_locked_out(username):
            security_logger.warning("Login attempt on locked account username=%s ip=%s", username, ip)
            form = self.get_form()
            form.add_error(None, "This account is temporarily locked due to too many failed attempts. Try again in 15 minutes.")
            return self.form_invalid(form)

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Successful login: clear lockout counter, log event."""
        user = form.get_user()
        ip = _get_client_ip(self.request)
        _clear_failed_attempts(user.username)
        _log_auth_event(user, "login", ip, f"Successful login for {user.username}")
        security_logger.info("Login success username=%s ip=%s", user.username, ip)
        return super().form_valid(form)

    def form_invalid(self, form):
        """Failed login: record attempt, log event."""
        username = self.request.POST.get("username", "").strip()
        ip = _get_client_ip(self.request)
        if username:
            _record_failed_attempt(username, ip)
            # Try to find user for audit log (may not exist)
            try:
                user = User.objects.get(username=username)
                _log_auth_event(user, "login_failed", ip, f"Failed login for {username}")
            except User.DoesNotExist:
                _log_auth_event(None, "login_failed", ip, f"Failed login for unknown user '{username}'")
            security_logger.warning("Login failed username=%s ip=%s", username, ip)
        return super().form_invalid(form)

    def get_success_url(self):
        # Always go through post-login check; pass through intended destination
        base = settings.LOGIN_REDIRECT_URL
        redirect_to = self.get_redirect_url()  # already validates safe URL
        if redirect_to:
            return base + "?" + urlencode({self.redirect_field_name: redirect_to})
        return base


BUSINESS_TYPE_INFO = [
    ("landscaping", "Landscaping", "\U0001F33F", "Lawn care, mowing, landscaping, irrigation"),
]


@require_http_methods(["GET", "POST"])
def signup(request):
    """Multi-step signup: Step 1 picks business type, Step 2 collects details."""
    if request.user.is_authenticated:
        return redirect("/")

    # Single business type — skip selection, go straight to account creation
    business_type = "landscaping"

    if request.method == "POST":
        form = SignUpForm(request.POST, business_type=business_type)
        if form.is_valid():
            business_name = form.cleaned_data.pop("business_name")
            business_subtype = form.cleaned_data.pop("business_subtype", "")
            business = Business.objects.create(
                name=business_name,
                business_type=business_type,
                business_subtype=business_subtype,
            )
            user = form.save(commit=False)
            user.business = business
            user.role = "owner"
            user.save()
            request.session.pop("signup_business_type", None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Auto-start 14-day free trial so user goes straight to onboarding
            from django.utils import timezone as _tz
            from datetime import timedelta as _td
            trial_days = 14
            business.subscription_status = "trialing"
            business.subscription_plan_tier = "core"  # Start on Pro
            business.subscription_current_period_end = _tz.now() + _td(days=trial_days)
            business.save(update_fields=["subscription_status", "subscription_plan_tier", "subscription_current_period_end"])

            messages.success(request, f"Welcome to FieldLgx! Your {trial_days}-day free trial is active.")
            return redirect("/")
    else:
        form = SignUpForm(business_type=business_type)

    type_label = dict(Business.BUSINESS_TYPE_CHOICES).get(business_type, business_type)
    return render(request, "registration/signup.html", {
        "form": form,
        "business_type": business_type,
        "business_type_label": type_label,
    })


@login_required
@require_http_methods(["GET", "POST"])
def social_signup_complete(request):
    """After social signup, collect business name and type to create a Business."""
    if request.user.business:
        return redirect("/subscription/status/")

    if not request.session.get("social_signup_pending"):
        return redirect("/")

    if request.method == "POST":
        form = SocialSignupCompleteForm(request.POST)
        if form.is_valid():
            business = Business.objects.create(
                name=form.cleaned_data["business_name"],
                business_type=form.cleaned_data["business_type"],
            )
            request.user.business = business
            request.user.role = "owner"
            request.user.save(update_fields=["business", "role"])
            request.session.pop("social_signup_pending", None)
            messages.success(request, f"Welcome! Your business '{business.name}' is set up.")
            return redirect("/subscription/status/")
    else:
        form = SocialSignupCompleteForm()

    return render(request, "registration/social_signup_complete.html", {
        "form": form,
        "business_types": BUSINESS_TYPE_INFO,
    })


@require_http_methods(["GET", "POST"])
def invite_accept(request, token):
    """Employee clicks invite link to join a business."""
    invite = get_object_or_404(EmployeeInvite, token=token)

    if invite.accepted:
        messages.info(request, "This invite has already been used.")
        return redirect("login")

    if invite.is_expired:
        messages.error(request, "This invite link has expired. Ask your employer for a new one.")
        return redirect("login")

    user = invite.user

    # If the employee is already logged in with the right account, just accept
    if request.user.is_authenticated:
        if request.user == user or request.user.email.lower() == invite.email.lower():
            # Link the logged-in user to the business
            if not request.user.business:
                request.user.business = invite.business
                request.user.role = invite.role
                request.user.save(update_fields=["business", "role"])
            invite.accepted = True
            invite.save(update_fields=["accepted"])
            messages.success(request, f"Welcome to {invite.business.name}!")
            return redirect("/")
        else:
            # Logged in as wrong user
            messages.warning(request, "You're signed in as a different account. Please sign out first.")
            return redirect("login")

    # Store invite token in session for the social auth adapter to pick up
    request.session["invite_token"] = token

    if request.method == "POST":
        # Setting a password
        pw_form = InviteSetPasswordForm(request.POST, user=user)
        if pw_form.is_valid():
            user.set_password(pw_form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            invite.accepted = True
            invite.save(update_fields=["accepted"])
            request.session.pop("invite_token", None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, f"Welcome to {invite.business.name}! You're all set.")
            return redirect("/")
    else:
        pw_form = InviteSetPasswordForm(user=user)

    return render(request, "registration/invite_accept.html", {
        "invite": invite,
        "pw_form": pw_form,
        "user_obj": user,
    })


@role_required("owner", "manager")
def employee_list(request):
    """List all employees (users in the owner's business)."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to manage employees.")
        return redirect("/")

    employees = User.objects.filter(business=business).order_by('role', 'first_name', 'last_name', 'username')
    return render(request, "accounts/employee_list.html", {"employees": employees})


@role_required("owner", "manager")
def employee_add(request):
    """Add a new employee via invite link — no password required."""
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business to add employees.")
        return redirect("/")

    if request.method == "POST":
        form = EmployeeInviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]

            # Check if a user with this email already exists in this business
            existing = User.objects.filter(email__iexact=email, business=business).first()
            if existing:
                messages.error(request, f"An employee with email {email} already exists.")
                return render(request, "accounts/employee_form.html", {
                    "form": form, "title": "Add Employee", "is_create": True,
                })

            # Generate unique username from email
            base = email.split("@")[0].lower()
            base = "".join(c for c in base if c.isalnum() or c == "_") or "user"
            username = base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1

            # Create user with unusable password
            user = User(
                username=username,
                email=email,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                role=form.cleaned_data["role"],
                business=business,
            )
            if form.cleaned_data.get("hourly_rate"):
                user.hourly_rate = form.cleaned_data["hourly_rate"]
            user.set_unusable_password()
            user.save()

            # Create invite
            invite = EmployeeInvite.objects.create(
                business=business,
                user=user,
                email=email,
                role=form.cleaned_data["role"],
            )

            invite_url = request.build_absolute_uri(f"/accounts/invite/{invite.token}/")
            messages.success(
                request,
                f"Employee '{user.get_full_name()}' created. Share their invite link so they can set up login."
            )
            return redirect("employee_edit", user_id=user.id)
    else:
        form = EmployeeInviteForm()

    return render(request, "accounts/employee_form.html", {
        "form": form,
        "title": "Add Employee",
        "is_create": True,
    })


@login_required
def account_profile(request):
    """User profile page with account deletion option."""
    return render(request, "accounts/profile.html")


@require_POST
@login_required
def delete_account(request):
    """Permanently delete the user's account and all associated data."""
    user = request.user
    confirm = request.POST.get("confirm", "").strip()

    if confirm != "DELETE":
        messages.error(request, "Please type DELETE to confirm account deletion.")
        return redirect("account_profile")

    business = getattr(user, "business", None)

    # If owner, check if they're the only owner
    if user.role == "owner" and business:
        other_owners = User.objects.filter(business=business, role="owner").exclude(id=user.id).count()
        if other_owners == 0:
            # This is the sole owner — delete the entire business
            business_name = business.name
            business.delete()  # CASCADE deletes all related data
            from django.contrib.auth import logout
            logout(request)
            messages.success(request, f"Your account and business '{business_name}' have been permanently deleted.")
            return redirect("/")

    # For crew/managers or owners with co-owners — just delete the user
    username = user.username
    from django.contrib.auth import logout
    logout(request)
    user.delete()
    messages.success(request, f"Your account '{username}' has been permanently deleted.")
    return redirect("/")


@require_POST
@role_required("owner", "manager")
def employee_update_color(request, user_id):
    """AJAX endpoint to update an employee's calendar color."""
    business = _get_business(request)
    if not business:
        return JsonResponse({"error": "No business"}, status=403)
    emp = get_object_or_404(User, id=user_id, business=business)
    data = json.loads(request.body) if request.body else {}
    color = (data.get("color") or "").strip()
    if color and not color.startswith("#"):
        color = "#" + color
    if color and len(color) in (4, 7) and all(c in "#0123456789abcdefABCDEF" for c in color):
        emp.color = color
    else:
        emp.color = ""
    emp.save(update_fields=["color"])
    return JsonResponse({"status": "ok", "color": emp.color})


@role_required("owner", "manager")
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

    # Check for pending invite link
    pending_invite = EmployeeInvite.objects.filter(user=employee, accepted=False).first()
    invite_url = None
    if pending_invite and pending_invite.is_valid:
        invite_url = request.build_absolute_uri(f"/accounts/invite/{pending_invite.token}/")

    return render(request, "accounts/employee_form.html", {
        "form": form,
        "employee": employee,
        "title": "Edit Employee",
        "is_create": False,
        "payments": payments,
        "total_paid": total_paid,
        "default_paid_date": default_paid_date,
        "invite_url": invite_url,
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


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def notification_send(request):
    """Owner or manager: send a notification to selected employees and/or crews (multi-select)."""
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
@require_http_methods(["GET", "POST"])
def notification_inbox(request):
    """Combined inbox + send page. Owners/managers can send from the 'Send' tab."""
    business = _get_business(request)
    notifications = (
        Notification.objects.filter(to_user=request.user)
        .select_related("from_user")
        .order_by("-created_at")[:100]
    )
    unread_count = Notification.objects.filter(to_user=request.user, read_at__isnull=True).count()

    # Send form for owners/managers
    send_form = None
    tab = request.GET.get("tab", "inbox")
    can_send = request.user.role in ("owner", "manager")
    if can_send:
        if request.method == "POST":
            send_form = SendNotificationForm(request.POST, business=business)
            if send_form.is_valid():
                msg = send_form.cleaned_data["message"].strip()
                if msg:
                    recipient_ids = set()
                    if send_form.cleaned_data.get("send_to_all"):
                        recipient_ids.update(
                            User.objects.filter(business=business)
                            .exclude(pk=request.user.pk)
                            .values_list("pk", flat=True)
                        )
                    else:
                        emp_ids = [int(x) for x in (send_form.cleaned_data.get("employees") or [])]
                        crew_ids = [int(x) for x in (send_form.cleaned_data.get("crews") or [])]
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
                            message=msg,
                        )
                        created += 1
                    if created:
                        messages.success(request, f"Notification sent to {created} employee(s).")
                    else:
                        messages.warning(request, "No recipients found.")
                    return redirect("notification_inbox")
            tab = "send"
        else:
            send_form = SendNotificationForm(business=business)

    return render(request, "accounts/notification_inbox.html", {
        "notifications": notifications,
        "unread_count": unread_count,
        "send_form": send_form,
        "can_send": can_send,
        "tab": tab,
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
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        from django.http import JsonResponse
        return JsonResponse({"ok": True})
    return redirect("notification_inbox")


@login_required
@require_http_methods(["POST"])
def push_subscribe(request):
    """Store a Web Push subscription for the current user."""
    import json as _json
    from django.http import JsonResponse
    from .models import PushSubscription
    try:
        data = _json.loads(request.body)
        endpoint = data.get("endpoint", "")
        keys = data.get("keys", {})
        p256dh = keys.get("p256dh", "")
        auth = keys.get("auth", "")
        if not endpoint or not p256dh or not auth:
            return JsonResponse({"error": "Invalid subscription"}, status=400)
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={"user": request.user, "p256dh": p256dh, "auth": auth},
        )
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def push_vapid_key(request):
    """Return the VAPID public key for push subscription."""
    from django.conf import settings as django_settings
    from django.http import JsonResponse
    key = getattr(django_settings, "VAPID_PUBLIC_KEY", "")
    return JsonResponse({"publicKey": key})


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
        form = EmployeePasswordForm(request.POST, user=employee)
        if form.is_valid():
            new_password = form.cleaned_data["new_password1"]
            employee.set_password(new_password)
            employee.save()
            messages.success(request, f"Password updated for {employee.get_full_name() or employee.username}.")
            return redirect("employee_edit", user_id=employee.id)
    else:
        form = EmployeePasswordForm(user=employee)

    return render(request, "accounts/employee_password.html", {
        "form": form,
        "employee": employee,
    })
