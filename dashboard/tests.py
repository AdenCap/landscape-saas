from pathlib import Path

from django.test import SimpleTestCase


class OwnerDashboardLightModeStyleTests(SimpleTestCase):
    def test_field_command_has_effective_light_theme_contrast_overrides(self):
        template = Path(__file__).resolve().parent / "templates" / "dashboard" / "owner_dashboard.html"
        content = template.read_text()

        self.assertIn("html.theme-light-effective .field-command", content)
        self.assertIn("--fc-ink: #172012", content)
        self.assertIn("--fc-muted: #465142", content)
        self.assertIn("--fc-dim: #5f6b5b", content)
        self.assertIn("html.theme-light-effective .fc-command-tile", content)
        self.assertIn("html.theme-light-effective .fc-stat strong", content)
