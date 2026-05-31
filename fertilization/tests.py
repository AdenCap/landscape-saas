from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from billing.models import FertilizerApplication, FertilizerProduct
from businesses.models import Business
from customers.models import Customer, Property
from fertilization.models import (
    CustomerProgramEnrollment,
    FertilizationProgram,
    ProgramRound,
    ScheduledRound,
)
from jobs.models import Job


class FertilizationEnrollmentWorkflowTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Fert Co",
            enabled_modules=["fertilization"],
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="fert-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="North Ridge",
        )
        self.property = Property.objects.create(
            customer=self.customer,
            address="42 Clover Ln",
            yard_sqft=12000,
        )
        self.program = FertilizationProgram.objects.create(
            business=self.business,
            name="Six Step Lawn",
        )
        for number, month in enumerate([3, 4, 5, 7, 9, 10], start=1):
            ProgramRound.objects.create(
                program=self.program,
                round_number=number,
                name=f"Application {number}",
                target_month_start=month,
                target_month_end=month,
            )
        self.client.force_login(self.owner)

    def test_enrollment_can_start_at_selected_application_round(self):
        response = self.client.post(
            reverse("fertilization:enrollment_list_create"),
            data={
                "property_id": self.property.id,
                "program_id": self.program.id,
                "year": "2026",
                "pricing_method": "per_application",
                "price_per_application": "65.00",
                "start_round_number": "4",
            },
        )

        self.assertEqual(response.status_code, 200)
        enrollment = CustomerProgramEnrollment.objects.get(property=self.property)
        self.assertEqual(
            list(enrollment.scheduled_rounds.order_by("round_number").values_list("round_number", flat=True)),
            [4, 5, 6],
        )

    def test_skipped_round_can_be_scheduled_later(self):
        enrollment = CustomerProgramEnrollment.objects.create(
            business=self.business,
            property=self.property,
            program=self.program,
            year=2026,
        )
        round_template = self.program.rounds.get(round_number=2)
        missed_round = ScheduledRound.objects.create(
            enrollment=enrollment,
            round_template=round_template,
            round_number=2,
            scheduled_date=date(2026, 4, 15),
            status="skipped",
            price=Decimal("75.00"),
        )

        response = self.client.post(
            reverse("fertilization:batch_schedule_rounds"),
            data={
                "round_ids": [str(missed_round.id)],
                "schedule_date": "2026-06-03",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        missed_round.refresh_from_db()
        self.assertEqual(missed_round.status, "scheduled")
        self.assertEqual(missed_round.scheduled_date, date(2026, 6, 3))
        self.assertIsNotNone(missed_round.job)
        self.assertEqual(missed_round.job.scheduled_date, date(2026, 6, 3))

    def test_client_profile_includes_manually_logged_fertilization_applications(self):
        product = FertilizerProduct.objects.create(
            business=self.business,
            name="Spring Weed Control",
            cost_per_pound=Decimal("2.00"),
        )
        FertilizerApplication.objects.create(
            business=self.business,
            property=self.property,
            product=product,
            application_date=date(2026, 4, 22),
            pounds_used=Decimal("40.00"),
            material_cost=Decimal("80.00"),
            charge_amount=Decimal("145.00"),
            notes="Spot sprayed front yard.",
        )
        Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 4, 12),
            status="completed",
            notes="Standard visit.",
        )

        response = self.client.get(reverse("customer_detail", args=[self.customer.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spring Weed Control")
        self.assertContains(response, "Spot sprayed front yard.")
