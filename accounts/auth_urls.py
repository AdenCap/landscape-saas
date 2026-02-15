"""Auth URLs under /accounts/: signup, login, logout, password reset, and 2FA (post-login check, verify, setup, revoke)."""
from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import twofa_views
from accounts.views import LoginView, signup

urlpatterns = [
    path("signup/", signup, name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password_change/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path("password_change/done/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # Two-factor: post-login check, verify (new device), setup, disable, revoke device
    path("post-login/", twofa_views.post_login_check, name="post_login_check"),
    path("2fa/setup/", twofa_views.twofa_setup, name="twofa_setup"),
    path("verify/", twofa_views.twofa_verify, name="twofa_verify"),
    path("2fa/disable/", twofa_views.twofa_disable, name="twofa_disable"),
    path("2fa/revoke-device/", twofa_views.twofa_revoke_device, name="twofa_revoke_device"),
]
