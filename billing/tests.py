import json
from decimal import Decimal
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from businesses.models import Business
from customers.models import Customer, ClientMessage, Property
from jobs.models import Job, JobServiceItem
from pricing.models import ServiceTemplate
from billing.models import (
    DocumentTemplate,
    Estimate,
    EstimateLineItem,
    Invoice,
    InvoiceLineItem,
    Promotion,
    PromotionRedemption,
)


class InvoiceLineItemPaymentTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Green Valley", subscription_status="active")
        self.owner = User.objects.create_user(
            username="owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(business=self.business, name="Acme Home")
        self.invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        self.mowing = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Mowing",
            quantity=1,
            unit_price=Decimal("85.00"),
        )
        self.landscaping = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Landscaping",
            quantity=1,
            unit_price=Decimal("240.00"),
        )
        self.client.force_login(self.owner)

    def test_owner_can_mark_single_line_item_paid_without_paying_invoice(self):
        response = self.client.post(
            reverse("billing:mark_invoice_line_item_paid", args=[self.invoice.id, self.mowing.id]),
            data={"action": "paid", "payment_method": "cash"},
        )

        self.assertRedirects(response, reverse("billing:invoice_detail", args=[self.invoice.id]))
        self.mowing.refresh_from_db()
        self.landscaping.refresh_from_db()
        self.invoice.refresh_from_db()

        self.assertTrue(self.mowing.is_paid)
        self.assertEqual(self.mowing.payment_method, "cash")
        self.assertIsNotNone(self.mowing.paid_at)
        self.assertEqual(self.mowing.paid_by, self.owner)
        self.assertFalse(self.landscaping.is_paid)
        self.assertEqual(self.invoice.status, "sent")

    def test_invoice_becomes_paid_when_all_line_items_are_paid(self):
        self.client.post(
            reverse("billing:mark_invoice_line_item_paid", args=[self.invoice.id, self.mowing.id]),
            data={"action": "paid", "payment_method": "cash"},
        )
        response = self.client.post(
            reverse("billing:mark_invoice_line_item_paid", args=[self.invoice.id, self.landscaping.id]),
            data={"action": "paid", "payment_method": "check"},
        )

        self.assertRedirects(response, reverse("billing:invoice_detail", args=[self.invoice.id]))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
        self.assertIsNotNone(self.invoice.paid_at)

    def test_unmarking_line_item_reopens_paid_invoice(self):
        self.mowing.is_paid = True
        self.mowing.save(update_fields=["is_paid"])
        self.landscaping.is_paid = True
        self.landscaping.save(update_fields=["is_paid"])
        self.invoice.status = "paid"
        self.invoice.save(update_fields=["status"])

        response = self.client.post(
            reverse("billing:mark_invoice_line_item_paid", args=[self.invoice.id, self.mowing.id]),
            data={"action": "unpaid"},
        )

        self.assertRedirects(response, reverse("billing:invoice_detail", args=[self.invoice.id]))
        self.mowing.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertFalse(self.mowing.is_paid)
        self.assertEqual(self.invoice.status, "sent")

    def test_line_item_edit_screen_exposes_payment_controls(self):
        response = self.client.get(reverse("billing:invoice_edit_line_items", args=[self.invoice.id]))

        self.assertContains(response, "Mark paid")
        self.assertContains(response, "Payment method")
        self.assertContains(
            response,
            reverse("billing:mark_invoice_line_item_paid", args=[self.invoice.id, self.mowing.id]),
        )

    def test_line_item_payment_can_return_to_edit_screen(self):
        edit_url = reverse("billing:invoice_edit_line_items", args=[self.invoice.id])

        response = self.client.post(
            reverse("billing:mark_invoice_line_item_paid", args=[self.invoice.id, self.mowing.id]),
            data={"action": "paid", "payment_method": "cash", "next": edit_url},
        )

        self.assertRedirects(response, edit_url)
        self.mowing.refresh_from_db()
        self.assertTrue(self.mowing.is_paid)

    def test_invoice_card_payment_toggle_accepts_form_posts(self):
        edit_url = reverse("billing:invoice_edit_line_items", args=[self.invoice.id])

        response = self.client.post(
            reverse("billing:invoice_toggle_card_payment", args=[self.invoice.id]),
            data={"next": edit_url},
        )

        self.assertRedirects(response, edit_url)
        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.enable_card_payment)

    def test_invoice_card_payment_toggle_accepts_json_posts(self):
        response = self.client.post(
            reverse("billing:invoice_toggle_card_payment", args=[self.invoice.id]),
            data=json.dumps({"enable": False}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.enable_card_payment)

    def test_invoice_list_does_not_show_duplicate_combine_panel(self):
        duplicate = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(
            invoice=duplicate,
            description="Cleanup",
            quantity=1,
            unit_price=Decimal("150.00"),
        )

        response = self.client.get(reverse("billing:invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Combine duplicate invoices")

    def test_invoice_detail_exposes_top_due_date_and_card_controls(self):
        self.business.stripe_connect_account_id = "acct_test"
        self.business.stripe_connect_charges_enabled = True
        self.business.client_card_payments_enabled = True
        self.business.save(update_fields=[
            "stripe_connect_account_id",
            "stripe_connect_charges_enabled",
            "client_card_payments_enabled",
        ])

        response = self.client.get(reverse("billing:invoice_detail", args=[self.invoice.id]))

        self.assertContains(response, "Save due date")
        self.assertContains(response, "Card payments")
        self.assertContains(response, "Accept cards: Yes")
        self.assertContains(response, 'id="card-payment-toggle"')

    def test_owner_can_update_invoice_due_date_from_detail_controls(self):
        response = self.client.post(
            reverse("billing:invoice_update_dates", args=[self.invoice.id]),
            data={"due_date": "2026-05-31"},
        )

        self.assertRedirects(response, reverse("billing:invoice_detail", args=[self.invoice.id]))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.due_date, date(2026, 5, 31))

    def test_invoice_command_center_exposes_actionable_totals(self):
        monthly = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            total=Decimal("410.00"),
        )
        InvoiceLineItem.objects.create(
            invoice=monthly,
            description="Monthly mowing",
            quantity=1,
            unit_price=Decimal("410.00"),
        )
        prop = Property.objects.create(customer=self.customer, address="123 Lawn Ave")
        job = Job.objects.create(property=prop, scheduled_date=date(2026, 4, 12), status="completed")
        JobServiceItem.objects.create(
            job=job,
            service=self.mowing.service if hasattr(self.mowing, "service") and self.mowing.service else ServiceTemplate.objects.create(
                business=self.business,
                name="Mowing",
                default_rate=Decimal("95.00"),
            ),
            description="Mowing",
            quantity=1,
            unit_price=Decimal("95.00"),
        )

        response = self.client.get(reverse("billing:invoice_list"))

        metrics = response.context["command_metrics"]
        self.assertEqual(metrics["draft_total"], Decimal("410.00"))
        self.assertEqual(metrics["monthly_draft_total"], Decimal("410.00"))
        self.assertEqual(metrics["unbilled_total"], Decimal("95.00"))
        self.assertEqual(metrics["unbilled_item_count"], 1)
        self.assertContains(response, "Work not invoiced")
        self.assertContains(response, "$95")

    def test_owner_can_combine_same_customer_draft_invoices(self):
        first = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
        )
        second = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
        )
        InvoiceLineItem.objects.create(invoice=first, description="Mowing", quantity=1, unit_price=Decimal("85.00"))
        InvoiceLineItem.objects.create(invoice=second, description="Cleanup", quantity=1, unit_price=Decimal("150.00"))

        response = self.client.post(
            reverse("billing:invoice_combine"),
            data={
                "target_invoice_id": first.id,
                "invoice_ids": [first.id, second.id],
            },
        )

        self.assertRedirects(response, reverse("billing:invoice_detail", args=[first.id]))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.line_items.count(), 2)
        self.assertEqual(first.total, Decimal("235.00"))
        self.assertEqual(second.status, "void")
        self.assertEqual(second.total, Decimal("0.00"))

    def test_combine_rejects_invoices_from_different_customers(self):
        other_customer = Customer.objects.create(business=self.business, name="Other Client")
        first = Invoice.objects.create(business=self.business, customer=self.customer, status="draft")
        second = Invoice.objects.create(business=self.business, customer=other_customer, status="draft")
        InvoiceLineItem.objects.create(invoice=first, description="Mowing", quantity=1, unit_price=Decimal("85.00"))
        InvoiceLineItem.objects.create(invoice=second, description="Cleanup", quantity=1, unit_price=Decimal("150.00"))

        response = self.client.post(
            reverse("billing:invoice_combine"),
            data={
                "target_invoice_id": first.id,
                "invoice_ids": [first.id, second.id],
            },
        )

        self.assertRedirects(response, reverse("billing:invoice_list"))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.line_items.count(), 1)
        self.assertEqual(second.status, "draft")

    def test_combine_without_target_invoice_redirects_instead_of_500(self):
        first = Invoice.objects.create(business=self.business, customer=self.customer, status="draft")
        second = Invoice.objects.create(business=self.business, customer=self.customer, status="draft")
        InvoiceLineItem.objects.create(invoice=first, description="Mowing", quantity=1, unit_price=Decimal("85.00"))
        InvoiceLineItem.objects.create(invoice=second, description="Cleanup", quantity=1, unit_price=Decimal("150.00"))

        response = self.client.post(
            reverse("billing:invoice_combine"),
            data={"invoice_ids": [first.id, second.id]},
        )

        self.assertRedirects(response, reverse("billing:invoice_list"))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.line_items.count(), 1)
        self.assertEqual(second.status, "draft")

    def test_apply_fixed_promotion_creates_discount_line_and_redemption(self):
        promo = Promotion.objects.create(
            business=self.business,
            name="Spring signup",
            code="SPRING25",
            promo_type="fixed_off",
            discount_value=Decimal("25.00"),
        )

        response = self.client.post(
            reverse("billing:invoice_apply_promotion", args=[self.invoice.id]),
            data={"promotion_id": promo.id},
        )

        self.assertRedirects(response, reverse("billing:invoice_detail", args=[self.invoice.id]))
        self.invoice.refresh_from_db()
        discount = self.invoice.line_items.get(is_discount=True)
        self.assertEqual(discount.promotion, promo)
        self.assertEqual(discount.line_total, Decimal("-25.00"))
        self.assertTrue(discount.is_paid)
        self.assertEqual(self.invoice.total, Decimal("300.00"))
        redemption = PromotionRedemption.objects.get(promotion=promo, invoice=self.invoice)
        self.assertEqual(redemption.customer, self.customer)
        self.assertEqual(redemption.discount_amount, Decimal("25.00"))


class MonthlyInvoiceRepairTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Green Valley",
            subscription_status="active",
        )
        self.owner = User.objects.create_user(
            username="monthly-repair-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="April Monthly Client",
            invoice_frequency="monthly",
        )
        self.property = Property.objects.create(customer=self.customer, address="42 April Ave")
        self.service = ServiceTemplate.objects.create(
            business=self.business,
            name="Mowing",
            default_rate=Decimal("110.00"),
        )
        self.client.force_login(self.owner)

    def _completed_job_item(self, scheduled_date, amount=Decimal("110.00")):
        job = Job.objects.create(
            property=self.property,
            scheduled_date=scheduled_date,
            status="completed",
        )
        return JobServiceItem.objects.create(
            job=job,
            service=self.service,
            description="Mowing",
            quantity=Decimal("1.00"),
            unit_price=amount,
        )

    def test_build_missing_monthly_drafts_collects_april_unbilled_jobs(self):
        first = self._completed_job_item(date(2026, 4, 5), Decimal("110.00"))
        second = self._completed_job_item(date(2026, 4, 19), Decimal("120.00"))
        may_item = self._completed_job_item(date(2026, 5, 3), Decimal("130.00"))

        response = self.client.post(
            reverse("billing:monthly_invoice_build_missing"),
            data={"year": "2026", "month": "4"},
        )

        self.assertRedirects(response, reverse("billing:monthly_invoice_list") + "?year=2026")
        first.refresh_from_db()
        second.refresh_from_db()
        may_item.refresh_from_db()
        invoice = Invoice.objects.get(customer=self.customer, period_start=date(2026, 4, 1))
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.total, Decimal("230.00"))
        self.assertEqual(first.billed_invoice, invoice)
        self.assertEqual(second.billed_invoice, invoice)
        self.assertIsNone(may_item.billed_invoice)

    def test_monthly_invoice_uses_clean_mowing_label_for_field_mowing_template(self):
        self.service.name = "Field Mowing"
        self.service.save(update_fields=["name"])
        job = Job.objects.create(
            property=self.property,
            scheduled_date=date(2026, 4, 5),
            status="completed",
        )
        JobServiceItem.objects.create(
            job=job,
            service=self.service,
            description="",
            quantity=Decimal("1.00"),
            unit_price=Decimal("110.00"),
        )

        response = self.client.post(
            reverse("billing:monthly_invoice_build_missing"),
            data={"year": "2026", "month": "4"},
        )

        self.assertRedirects(response, reverse("billing:monthly_invoice_list") + "?year=2026")
        invoice = Invoice.objects.get(customer=self.customer, period_start=date(2026, 4, 1))
        line = invoice.line_items.get()
        self.assertEqual(line.description, "Mowing - 42 April Ave (2026-04-05)")

    def test_monthly_queue_shows_line_item_preview_and_individual_send(self):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Weekly mowing - April 5",
            quantity=1,
            unit_price=Decimal("110.00"),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Spring cleanup add-on",
            quantity=1,
            unit_price=Decimal("250.00"),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Mulch bed cleanup",
            quantity=1,
            unit_price=Decimal("140.00"),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Edging",
            quantity=1,
            unit_price=Decimal("45.00"),
        )

        response = self.client.get(reverse("billing:monthly_invoice_list") + "?year=2026")

        self.assertContains(response, "Weekly mowing - April 5")
        self.assertContains(response, "Spring cleanup add-on")
        self.assertContains(response, "Mulch bed cleanup")
        self.assertContains(response, "Edging")
        self.assertNotContains(response, "+1 more")
        self.assertContains(response, 'name="invoice_ids" value="%s"' % invoice.id)
        self.assertContains(response, "Send invoice")

    def test_unbilled_work_page_lists_completed_uninvoiced_items(self):
        item = self._completed_job_item(date(2026, 4, 12), Decimal("115.00"))

        response = self.client.get(reverse("billing:unbilled_work"))

        self.assertContains(response, "Work to be billed")
        self.assertContains(response, item.description)
        self.assertContains(response, "$115")


class DocumentTemplateStudioTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Green Valley", subscription_status="active")
        self.owner = User.objects.create_user(
            username="template-owner",
            password="password",
            role="owner",
            business=self.business,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Acme Home",
            email="client@example.com",
            phone="555-0100",
        )
        self.client.force_login(self.owner)
        self.business.contact_phone = "555-0111"
        self.business.contact_email = "office@greenvalley.test"
        self.business.website_url = "https://greenvalley.test"
        self.business.save(update_fields=["contact_phone", "contact_email", "website_url"])

    def test_owner_can_save_visible_template_options(self):
        response = self.client.post(
            reverse("billing:document_template_edit", args=["estimate"]),
            data={
                "template_key": "luxury",
                "name": "High End Proposal",
                "primary_color": "#88cc44",
                "font_style": "serif",
                "show_property_address": "on",
                "show_service_date": "on",
                "header_text": "Licensed and insured.",
                "footer_text": "Thank you for choosing us.",
                "terms_and_conditions": "Valid for 30 days.",
                "payment_instructions": "Deposit due on approval.",
                "custom_field_key": ["promo_code"],
                "custom_field_label": ["Promotion code"],
                "custom_field_type": ["text"],
                "custom_field_required_0": "on",
            },
        )

        self.assertRedirects(response, reverse("billing:document_template_edit", args=["estimate"]))
        template = DocumentTemplate.objects.get(business=self.business, doc_type="estimate")
        self.assertEqual(template.template_key, "luxury")
        self.assertEqual(template.primary_color, "#88cc44")
        self.assertEqual(template.font_style, "serif")
        self.assertTrue(template.show_property_address)
        self.assertTrue(template.show_service_date)
        self.assertFalse(template.show_photos)
        self.assertEqual(template.payment_instructions, "Deposit due on approval.")
        self.assertEqual(template.custom_fields[0]["key"], "promo_code")
        self.assertTrue(template.custom_fields[0]["required"])

    def test_estimate_and_invoice_pdfs_generate_with_template_settings(self):
        long_header = (
            "Header message explains the scope, schedule expectations, access notes, and the complete customer "
            "experience without being clipped at the first line."
        )
        long_terms = (
            "Terms and conditions include weather delays, access requirements, utility responsibility, change "
            "approval, payment timing, and all other owner-provided language."
        )
        long_payment = (
            "Payment instructions include card, check, ACH, deposit handling, monthly billing, card-on-file "
            "authorization, and office contact details."
        )
        long_footer = (
            "Footer message thanks the customer, explains how to reach the office, and stays visible in the PDF "
            "instead of being dropped."
        )
        DocumentTemplate.objects.create(
            business=self.business,
            doc_type="estimate",
            name="Proposal",
            template_key="modern_dark",
            primary_color="#88cc44",
            header_text=long_header,
            terms_and_conditions=long_terms,
            payment_instructions=long_payment,
            footer_text=long_footer,
        )
        DocumentTemplate.objects.create(
            business=self.business,
            doc_type="invoice",
            name="Invoice",
            template_key="clean_light",
            primary_color="#88cc44",
            header_text=long_header,
            terms_and_conditions=long_terms,
            payment_instructions=long_payment,
            footer_text=long_footer,
        )
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Spring cleanup",
            deposit_required=True,
            deposit_type="fixed",
            deposit_amount=Decimal("100.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Cleanup",
            quantity=1,
            unit_price=Decimal("300.00"),
        )
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Mowing",
            quantity=1,
            unit_price=Decimal("85.00"),
        )

        from billing import views as billing_views

        with patch("billing.views._pdf_draw_full_text_section", wraps=billing_views._pdf_draw_full_text_section) as draw_section, \
             patch("billing.views._pdf_draw_closing_footer_message", wraps=billing_views._pdf_draw_closing_footer_message) as draw_footer_message:
            estimate_response = self.client.get(reverse("billing:estimate_pdf", args=[estimate.id]) + "?inline=1")
            invoice_response = self.client.get(reverse("billing:invoice_pdf", args=[invoice.id]) + "?inline=1")

        estimate_bytes = b"".join(estimate_response.streaming_content)
        invoice_bytes = b"".join(invoice_response.streaming_content)
        self.assertEqual(estimate_response.status_code, 200)
        self.assertEqual(invoice_response.status_code, 200)
        self.assertTrue(estimate_bytes.startswith(b"%PDF"))
        self.assertTrue(invoice_bytes.startswith(b"%PDF"))
        self.assertGreater(len(estimate_bytes), 1000)
        self.assertGreater(len(invoice_bytes), 1000)
        drawn_texts = [call.kwargs["text"] for call in draw_section.call_args_list if "text" in call.kwargs]
        for expected in [long_header, long_terms, long_payment]:
            self.assertIn(expected, drawn_texts)
        self.assertNotIn(long_footer, drawn_texts)
        footer_texts = [call.args[2] for call in draw_footer_message.call_args_list]
        self.assertEqual(footer_texts.count(long_footer), 2)
        self.assertIn("greenvalley.test", billing_views._pdf_business_contact_lines(self.business))

    def test_client_accept_includes_selected_optional_items(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Spring cleanup",
            status="sent",
            view_token="client-token",
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Base cleanup",
            quantity=1,
            unit_price=Decimal("300.00"),
        )
        optional = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Mulch refresh",
            quantity=1,
            unit_price=Decimal("125.00"),
            is_addon=True,
        )

        response = self.client.post(
            reverse("billing:estimate_client_accept", args=[estimate.id, "client-token"]),
            data={"optional_items": [str(optional.id)]},
        )

        estimate.refresh_from_db()
        self.assertRedirects(response, reverse("billing:estimate_client_accepted", args=[estimate.id, "client-token"]))
        self.assertEqual(estimate.status, "accepted")
        self.assertEqual(estimate.accepted_total, Decimal("425.00"))
        self.assertEqual(estimate.accepted_optional_item_ids, [optional.id])

    @patch("businesses.email_sender.is_email_configured", return_value=True)
    @patch("businesses.email_sender.send_business_email")
    def test_client_accept_owner_email_separates_accepted_and_declined_optional_items(self, mock_send, _mock_configured):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Spring cleanup",
            status="sent",
            view_token="email-token",
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Base cleanup",
            quantity=1,
            unit_price=Decimal("300.00"),
        )
        selected = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Mulch refresh",
            quantity=1,
            unit_price=Decimal("125.00"),
            is_addon=True,
        )
        declined = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Seasonal color",
            quantity=1,
            unit_price=Decimal("95.00"),
            is_addon=True,
        )

        response = self.client.post(
            reverse("billing:estimate_client_accept", args=[estimate.id, "email-token"]),
            data={"optional_items": [str(selected.id)]},
        )

        self.assertRedirects(response, reverse("billing:estimate_client_accepted", args=[estimate.id, "email-token"]))
        body_text = mock_send.call_args.kwargs["body_text"]
        self.assertIn("Accepted Work:", body_text)
        self.assertIn("Optional Items Not Accepted:", body_text)
        self.assertIn("Base cleanup", body_text)
        self.assertIn("Mulch refresh", body_text)
        self.assertIn("Seasonal color", body_text)
        self.assertNotIn("Line Items:", body_text)

    def test_owner_can_mark_sent_estimate_accepted(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Backyard cleanup",
            status="sent",
            view_token="owner-accept-token",
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Cleanup",
            quantity=2,
            unit_price=Decimal("125.00"),
        )

        response = self.client.post(reverse("billing:estimate_owner_accept", args=[estimate.id]))

        self.assertRedirects(response, reverse("billing:estimate_detail", args=[estimate.id]))
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, "accepted")
        self.assertIsNotNone(estimate.accepted_at)
        self.assertEqual(estimate.accepted_total, Decimal("250.00"))
        self.assertEqual(estimate.accepted_optional_item_ids, [])

    def test_owner_accept_can_include_selected_optional_items(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Backyard renovation",
            status="sent",
            view_token="owner-optional-token",
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Base renovation",
            quantity=1,
            unit_price=Decimal("1000.00"),
        )
        lighting = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Landscape lighting",
            quantity=1,
            unit_price=Decimal("450.00"),
            is_addon=True,
        )
        mulch = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Premium mulch",
            quantity=1,
            unit_price=Decimal("225.00"),
            is_addon=True,
        )

        response = self.client.post(
            reverse("billing:estimate_owner_accept", args=[estimate.id]),
            data={"optional_items": [str(lighting.id)]},
        )

        self.assertRedirects(response, reverse("billing:estimate_detail", args=[estimate.id]))
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, "accepted")
        self.assertEqual(estimate.accepted_total, Decimal("1450.00"))
        self.assertEqual(estimate.accepted_optional_item_ids, [lighting.id])
        self.assertNotIn(mulch.id, estimate.accepted_optional_item_ids)

    def test_owner_accept_can_decline_all_optional_items(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Front bed refresh",
            status="sent",
            view_token="owner-no-options-token",
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Bed cleanup",
            quantity=1,
            unit_price=Decimal("300.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Annual color",
            quantity=1,
            unit_price=Decimal("175.00"),
            is_addon=True,
        )

        response = self.client.post(reverse("billing:estimate_owner_accept", args=[estimate.id]))

        self.assertRedirects(response, reverse("billing:estimate_detail", args=[estimate.id]))
        estimate.refresh_from_db()
        self.assertEqual(estimate.accepted_total, Decimal("300.00"))
        self.assertEqual(estimate.accepted_optional_item_ids, [])

    def test_estimate_conversion_preserves_line_item_quantity_and_unit_price(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Mulch install",
            status="accepted",
            accepted_total=Decimal("250.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Mulch bed",
            quantity=2,
            unit_price=Decimal("125.00"),
        )

        response = self.client.post(reverse("billing:convert_estimate_to_invoice", args=[estimate.id]))

        self.assertEqual(response.status_code, 302)
        invoice_id = response["Location"].rstrip("/").split("/")[-1]
        invoice = Invoice.objects.get(id=invoice_id)
        item = invoice.line_items.get()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("125.00"))
        self.assertEqual(invoice.total, Decimal("250.00"))

    def test_estimate_conversion_includes_only_accepted_optional_items(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Landscape install",
            status="accepted",
            accepted_total=Decimal("1450.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Base install",
            quantity=1,
            unit_price=Decimal("1000.00"),
        )
        selected = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Lighting",
            quantity=1,
            unit_price=Decimal("450.00"),
            is_addon=True,
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Extra mulch",
            quantity=1,
            unit_price=Decimal("225.00"),
            is_addon=True,
        )
        estimate.accepted_optional_item_ids = [selected.id]
        estimate.save(update_fields=["accepted_optional_item_ids"])

        response = self.client.post(reverse("billing:convert_estimate_to_invoice", args=[estimate.id]))

        self.assertEqual(response.status_code, 302)
        invoice_id = response["Location"].rstrip("/").split("/")[-1]
        invoice = Invoice.objects.get(id=invoice_id)
        descriptions = list(invoice.line_items.order_by("id").values_list("description", flat=True))
        self.assertEqual(descriptions, ["Base install", "Lighting (add-on)"])
        self.assertEqual(invoice.total, Decimal("1450.00"))

    def test_legacy_estimate_conversion_keeps_old_addon_total_behavior(self):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Legacy accepted estimate",
            status="accepted",
            accepted_total=Decimal("600.00"),
            accepted_optional_item_ids=None,
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Base cleanup",
            quantity=1,
            unit_price=Decimal("400.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Leaf haul away",
            quantity=1,
            unit_price=Decimal("200.00"),
            is_addon=True,
        )

        response = self.client.post(reverse("billing:convert_estimate_to_invoice", args=[estimate.id]))

        self.assertEqual(response.status_code, 302)
        invoice_id = response["Location"].rstrip("/").split("/")[-1]
        invoice = Invoice.objects.get(id=invoice_id)
        descriptions = list(invoice.line_items.order_by("id").values_list("description", flat=True))
        self.assertEqual(descriptions, ["Base cleanup", "Leaf haul away (add-on)"])
        self.assertEqual(invoice.total, Decimal("600.00"))

    def test_card_payments_can_be_disabled_for_client_deposits(self):
        self.business.stripe_connect_account_id = "acct_test"
        self.business.stripe_connect_charges_enabled = True
        self.business.client_card_payments_enabled = False
        self.business.save(update_fields=[
            "stripe_connect_account_id",
            "stripe_connect_charges_enabled",
            "client_card_payments_enabled",
        ])
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Patio install",
            status="sent",
            view_token="deposit-token",
            deposit_required=True,
            deposit_type="fixed",
            deposit_amount=Decimal("250.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Patio",
            quantity=1,
            unit_price=Decimal("1200.00"),
        )

        response = self.client.post(reverse("billing:estimate_client_accept", args=[estimate.id, "deposit-token"]))

        estimate.refresh_from_db()
        self.assertRedirects(response, reverse("billing:estimate_client_accepted", args=[estimate.id, "deposit-token"]))
        self.assertEqual(estimate.status, "accepted")
        self.assertFalse(estimate.deposit_paid)

    @patch("billing.views._stripe_connect_enabled", return_value=True)
    @patch("billing.views.stripe.checkout.Session.create")
    def test_accept_with_card_deposit_redirects_to_stripe_checkout(self, mock_create, _mock_enabled):
        mock_create.return_value.id = "cs_test_deposit"
        mock_create.return_value.url = "https://checkout.stripe.test/session"
        self.business.stripe_connect_account_id = "acct_test"
        self.business.stripe_connect_charges_enabled = True
        self.business.client_card_payments_enabled = True
        self.business.save(update_fields=[
            "stripe_connect_account_id",
            "stripe_connect_charges_enabled",
            "client_card_payments_enabled",
        ])
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Landscape install",
            status="sent",
            view_token="stripe-token",
            deposit_required=True,
            deposit_type="percent",
            deposit_amount=Decimal("10.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Base",
            quantity=1,
            unit_price=Decimal("1000.00"),
        )
        optional = EstimateLineItem.objects.create(
            estimate=estimate,
            description="Lighting",
            quantity=1,
            unit_price=Decimal("500.00"),
            is_addon=True,
        )

        response = self.client.post(
            reverse("billing:estimate_client_accept", args=[estimate.id, "stripe-token"]),
            data={"optional_items": [str(optional.id)]},
        )

        estimate.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://checkout.stripe.test/session")
        self.assertEqual(estimate.accepted_total, Decimal("1500.00"))
        self.assertEqual(estimate.stripe_deposit_checkout_session_id, "cs_test_deposit")
        call_kwargs = mock_create.call_args.kwargs
        self.assertEqual(call_kwargs["line_items"][0]["price_data"]["unit_amount"], 15000)
        self.assertEqual(call_kwargs["metadata"]["payment_type"], "estimate_deposit")

    @patch("stripe.PaymentIntent.retrieve", side_effect=Exception("skip network"))
    def test_checkout_webhook_marks_estimate_deposit_paid(self, _mock_retrieve):
        from subscription.handlers import handle_stripe_webhook

        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Spring cleanup",
            status="accepted",
            view_token="paid-token",
            deposit_required=True,
            deposit_type="fixed",
            deposit_amount=Decimal("100.00"),
            accepted_total=Decimal("500.00"),
        )

        handle_stripe_webhook({
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_paid_deposit",
                    "mode": "payment",
                    "payment_intent": "pi_paid_deposit",
                    "metadata": {
                        "estimate_id": str(estimate.id),
                        "payment_type": "estimate_deposit",
                    },
                }
            },
        })

        estimate.refresh_from_db()
        self.assertTrue(estimate.deposit_paid)
        self.assertIsNotNone(estimate.deposit_paid_at)
        self.assertEqual(estimate.stripe_deposit_checkout_session_id, "cs_paid_deposit")
        self.assertEqual(estimate.stripe_deposit_payment_intent_id, "pi_paid_deposit")

    def test_estimate_detail_shows_owner_payment_readiness_and_client_preview(self):
        self.business.client_card_payments_enabled = False
        self.business.save(update_fields=["client_card_payments_enabled"])
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Patio refresh",
            status="sent",
            view_token="owner-preview-token",
            deposit_required=True,
            deposit_type="fixed",
            deposit_amount=Decimal("150.00"),
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Patio refresh",
            quantity=1,
            unit_price=Decimal("900.00"),
        )

        response = self.client.get(reverse("billing:estimate_detail", args=[estimate.id]))

        self.assertContains(response, "Payment readiness")
        self.assertContains(response, "Client preview")
        self.assertContains(response, "Card payments off")
        self.assertContains(response, "Deposit pending")

    def test_invoice_detail_shows_owner_payment_readiness(self):
        self.business.client_card_payments_enabled = False
        self.business.save(update_fields=["client_card_payments_enabled"])
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Mowing",
            quantity=1,
            unit_price=Decimal("85.00"),
        )

        response = self.client.get(reverse("billing:invoice_detail", args=[invoice.id]))

        self.assertContains(response, "Payment readiness")
        self.assertContains(response, "Client pay page")
        self.assertContains(response, "Card payments off")

    def test_public_invoice_pay_page_shows_manual_methods_when_card_is_off(self):
        self.business.client_card_payments_enabled = False
        self.business.venmo_username = "greenvalley"
        self.business.zelle_email_or_phone = "pay@example.com"
        self.business.save(update_fields=["client_card_payments_enabled", "venmo_username", "zelle_email_or_phone"])
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            payment_token="pay-token",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(invoice=invoice, description="Mowing", quantity=1, unit_price=Decimal("85.00"))

        response = self.client.get(reverse("billing:invoice_pay_page", args=[invoice.id, "pay-token"]))

        self.assertContains(response, "Choose a payment method")
        self.assertContains(response, "Venmo")
        self.assertContains(response, "Zelle")
        self.assertContains(response, "I sent payment")
        self.assertNotContains(response, "Pay securely by card")

    def test_estimate_accepted_shows_manual_deposit_methods_when_card_is_off(self):
        self.business.client_card_payments_enabled = False
        self.business.venmo_username = "greenvalley"
        self.business.save(update_fields=["client_card_payments_enabled", "venmo_username"])
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Spring cleanup",
            status="accepted",
            view_token="accepted-token",
            accepted_total=Decimal("500.00"),
            deposit_required=True,
            deposit_type="fixed",
            deposit_amount=Decimal("100.00"),
        )

        response = self.client.get(reverse("billing:estimate_client_accepted", args=[estimate.id, "accepted-token"]))

        self.assertContains(response, "Deposit due")
        self.assertContains(response, "Venmo")
        self.assertContains(response, "greenvalley")

    @patch("billing.views.stripe.PaymentIntent.create")
    def test_saved_card_charge_respects_business_saved_card_setting(self, mock_create):
        self.business.stripe_connect_account_id = "acct_test"
        self.business.stripe_connect_charges_enabled = True
        self.business.client_card_payments_enabled = True
        self.business.client_saved_cards_enabled = False
        self.business.save(update_fields=[
            "stripe_connect_account_id",
            "stripe_connect_charges_enabled",
            "client_card_payments_enabled",
            "client_saved_cards_enabled",
        ])
        self.customer.stripe_customer_id = "cus_test"
        self.customer.stripe_payment_method_id = "pm_test"
        self.customer.card_brand = "visa"
        self.customer.card_last4 = "4242"
        self.customer.save(update_fields=[
            "stripe_customer_id",
            "stripe_payment_method_id",
            "card_brand",
            "card_last4",
        ])
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Mowing",
            quantity=1,
            unit_price=Decimal("85.00"),
        )

        response = self.client.post(reverse("billing:charge_invoice_card_on_file", args=[invoice.id]))

        invoice.refresh_from_db()
        self.assertRedirects(response, reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(invoice.status, "sent")
        mock_create.assert_not_called()

    def test_customer_detail_shows_separate_auto_charge_preferences(self):
        self.customer.stripe_payment_method_id = "pm_test"
        self.customer.stripe_customer_id = "cus_test"
        self.customer.card_brand = "visa"
        self.customer.card_last4 = "4242"
        self.customer.auto_charge_completed_jobs = True
        self.customer.auto_charge_monthly_invoices = False
        self.customer.save(update_fields=[
            "stripe_payment_method_id",
            "stripe_customer_id",
            "card_brand",
            "card_last4",
            "auto_charge_completed_jobs",
            "auto_charge_monthly_invoices",
        ])

        response = self.client.get(reverse("customer_detail", args=[self.customer.id]))

        self.assertContains(response, "Auto-charge after each completed service")
        self.assertContains(response, "Auto-charge monthly invoices")
        self.assertContains(response, "Visa ending 4242")

    @patch("billing.services.stripe.PaymentIntent.create")
    def test_monthly_invoice_auto_charge_uses_monthly_customer_preference(self, mock_create):
        mock_create.return_value.status = "succeeded"
        mock_create.return_value.id = "pi_monthly"
        mock_create.return_value.latest_charge = "ch_monthly"
        self.business.stripe_connect_account_id = "acct_test"
        self.business.stripe_connect_charges_enabled = True
        self.business.client_card_payments_enabled = True
        self.business.save(update_fields=[
            "stripe_connect_account_id",
            "stripe_connect_charges_enabled",
            "client_card_payments_enabled",
        ])
        self.customer.stripe_payment_method_id = "pm_test"
        self.customer.stripe_customer_id = "cus_test"
        self.customer.card_brand = "visa"
        self.customer.card_last4 = "4242"
        self.customer.auto_charge_completed_jobs = True
        self.customer.auto_charge_monthly_invoices = False
        self.customer.save(update_fields=[
            "stripe_payment_method_id",
            "stripe_customer_id",
            "card_brand",
            "card_last4",
            "auto_charge_completed_jobs",
            "auto_charge_monthly_invoices",
        ])
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
            period_start="2026-04-01",
            period_end="2026-04-30",
        )
        InvoiceLineItem.objects.create(invoice=invoice, description="April mowing", quantity=1, unit_price=Decimal("200.00"))

        response = self.client.post(reverse("billing:send_invoice", args=[invoice.id]))

        invoice.refresh_from_db()
        self.assertRedirects(response, reverse("billing:invoice_detail", args=[invoice.id]))
        self.assertEqual(invoice.status, "sent")
        mock_create.assert_not_called()

        self.customer.auto_charge_monthly_invoices = True
        self.customer.save(update_fields=["auto_charge_monthly_invoices"])
        invoice2 = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
            period_start="2026-05-01",
            period_end="2026-05-31",
        )
        InvoiceLineItem.objects.create(invoice=invoice2, description="May mowing", quantity=1, unit_price=Decimal("200.00"))

        self.client.post(reverse("billing:send_invoice", args=[invoice2.id]))

        invoice2.refresh_from_db()
        self.assertEqual(invoice2.status, "paid")
        mock_create.assert_called_once()

    @patch("businesses.email_sender.is_email_configured", return_value=True)
    @patch("businesses.email_sender.send_business_email", return_value=(True, "ok"))
    def test_estimate_followup_sends_email_and_records_message(self, mock_send, _mock_configured):
        estimate = Estimate.objects.create(
            business=self.business,
            customer=self.customer,
            title="Spring cleanup",
            status="sent",
            view_token="followup-token",
        )
        EstimateLineItem.objects.create(
            estimate=estimate,
            description="Cleanup",
            quantity=1,
            unit_price=Decimal("300.00"),
        )

        response = self.client.post(reverse("billing:estimate_send_followup", args=[estimate.id]))

        estimate.refresh_from_db()
        self.assertRedirects(response, reverse("billing:estimate_detail", args=[estimate.id]))
        self.assertIsNotNone(estimate.last_follow_up_at)
        self.assertTrue(ClientMessage.objects.filter(customer=self.customer, subject__icontains="Spring cleanup").exists())
        mock_send.assert_called_once()

    @patch("businesses.email_sender.is_email_configured", return_value=True)
    @patch("businesses.email_sender.send_business_email", return_value=(True, "ok"))
    def test_invoice_reminder_sends_email_and_returns_to_invoice(self, mock_send, _mock_configured):
        invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="sent",
            payment_token="invoice-reminder-token",
            due_date=date(2026, 4, 1),
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(invoice=invoice, description="Mowing", quantity=1, unit_price=Decimal("85.00"))

        response = self.client.post(reverse("billing:send_reminder", args=[invoice.id]))

        self.assertRedirects(response, reverse("billing:invoice_detail", args=[invoice.id]))
        mock_send.assert_called_once()
        self.assertIn("Payment Reminder", mock_send.call_args.kwargs["subject"])

    @patch("billing.services.stripe.PaymentIntent.create")
    @patch("businesses.email_sender.is_email_configured", return_value=True)
    @patch("businesses.email_sender.send_business_email", return_value=(True, "ok"))
    def test_monthly_batch_send_approves_selected_drafts(self, mock_send, _mock_configured, mock_payment):
        mock_payment.return_value.status = "succeeded"
        mock_payment.return_value.id = "pi_batch"
        mock_payment.return_value.latest_charge = "ch_batch"
        first = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
        )
        second = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
        )
        other = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            status="draft",
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("0"),
        )
        InvoiceLineItem.objects.create(invoice=first, description="April mowing", quantity=1, unit_price=Decimal("200.00"))
        InvoiceLineItem.objects.create(invoice=second, description="May mowing", quantity=1, unit_price=Decimal("225.00"))
        InvoiceLineItem.objects.create(invoice=other, description="One-time cleanup", quantity=1, unit_price=Decimal("150.00"))

        response = self.client.post(
            reverse("billing:monthly_invoice_batch_send"),
            data={"invoice_ids": [str(first.id), str(second.id), str(other.id)]},
        )

        self.assertRedirects(response, reverse("billing:monthly_invoice_list"))
        first.refresh_from_db()
        second.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "sent")
        self.assertEqual(other.status, "draft")
        self.assertEqual(first.approved_by, self.owner)
        self.assertTrue(first.payment_token)
        self.assertTrue(second.payment_token)
        self.assertEqual(mock_send.call_count, 2)
