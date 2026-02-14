from decimal import Decimal
from pricing.models import ServiceTemplate


def get_effective_rate(property_obj, service_template):
    override = property_obj.service_rates.filter(service=service_template).first()
    if override and override.override_rate is not None:
        return service_template.default_unit, Decimal(str(override.override_rate))
    return service_template.default_unit, Decimal(str(service_template.default_rate))
