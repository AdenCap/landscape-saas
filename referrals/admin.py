from django.contrib import admin
from .models import Referral


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referrer', 'referred_name', 'status', 'referral_code', 'created_at']
    list_filter = ['status', 'reward_paid', 'created_at']
    search_fields = ['referrer__name', 'referred_name', 'referral_code']
    readonly_fields = ['referral_code', 'created_at', 'converted_at']
