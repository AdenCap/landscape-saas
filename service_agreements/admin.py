from django.contrib import admin
from .models import ServiceAgreement, AgreementVisit


@admin.register(ServiceAgreement)
class ServiceAgreementAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "customer", "status", "start_date", "end_date"]
    list_filter = ["business", "status", "agreement_type"]
    search_fields = ["name"]


@admin.register(AgreementVisit)
class AgreementVisitAdmin(admin.ModelAdmin):
    list_display = ["agreement", "scheduled_date", "status"]
    list_filter = ["status"]
