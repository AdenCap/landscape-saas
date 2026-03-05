"""
Auto-pricing engine for fertilization programs.

All functions are pure calculators — they take data in and return numbers.
No database writes happen here.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import math


def calculate_lbs_needed(application_rate, square_feet):
    """Calculate pounds of product needed for a given area.

    Args:
        application_rate: lbs per 1,000 sqft (Decimal or float)
        square_feet: total area in sqft (int or Decimal)

    Returns:
        Decimal: total pounds needed, rounded to 2 decimal places
    """
    rate = Decimal(str(application_rate))
    sqft = Decimal(str(square_feet))
    lbs = rate * sqft / Decimal('1000')
    return lbs.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_bags_needed(lbs_needed, lbs_per_bag):
    """Calculate whole bags needed (rounds up).

    Args:
        lbs_needed: total pounds of product needed
        lbs_per_bag: pounds per bag

    Returns:
        int: number of bags (rounded up using ROUND_CEILING)
    """
    lbs = Decimal(str(lbs_needed))
    per_bag = Decimal(str(lbs_per_bag))

    if per_bag <= 0:
        return 0
    if lbs <= 0:
        return 0

    bags = (lbs / per_bag).quantize(Decimal('1'), rounding=ROUND_CEILING)
    return int(bags)


def calculate_round_material_cost(products_with_rates, square_feet):
    """Calculate total material cost for one round.

    Args:
        products_with_rates: list of dicts with keys:
            - product: FertilizerProduct instance
            - rate_override: Decimal or None (overrides product.application_rate)
        square_feet: property lawn area

    Returns:
        dict with:
            - total_cost: Decimal
            - product_details: list of dicts per product with lbs_needed, cost
    """
    sqft = Decimal(str(square_feet))
    total_cost = Decimal('0')
    product_details = []

    if sqft <= 0:
        return {
            'total_cost': Decimal('0.00'),
            'product_details': [],
        }

    for item in products_with_rates:
        product = item['product']
        rate_override = item.get('rate_override')

        # Determine application rate: override takes priority, then product default
        if rate_override is not None:
            rate = Decimal(str(rate_override))
        elif product.application_rate is not None:
            rate = Decimal(str(product.application_rate))
        else:
            # No rate available — skip this product
            product_details.append({
                'product': product,
                'lbs_needed': Decimal('0.00'),
                'cost': Decimal('0.00'),
            })
            continue

        lbs_needed = calculate_lbs_needed(rate, sqft)
        cost = product.calculate_cost(lbs_needed)

        product_details.append({
            'product': product,
            'lbs_needed': lbs_needed,
            'cost': cost,
        })
        total_cost += cost

    return {
        'total_cost': total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'product_details': product_details,
    }


def calculate_program_material_cost(program, square_feet):
    """Calculate total material cost for an entire program (all rounds).

    Args:
        program: FertilizationProgram instance (with rounds prefetched)
        square_feet: property lawn area

    Returns:
        dict with:
            - total_cost: Decimal
            - round_costs: list of dicts per round with round, cost, product_details
    """
    total_cost = Decimal('0')
    round_costs = []

    rounds = program.rounds.all()
    if not rounds:
        return {
            'total_cost': Decimal('0.00'),
            'round_costs': [],
        }

    for rnd in rounds:
        products = rnd.products.all()
        products_with_rates = []
        for product in products:
            products_with_rates.append({
                'product': product,
                'rate_override': rnd.default_rate_override,
            })

        round_result = calculate_round_material_cost(products_with_rates, square_feet)
        round_costs.append({
            'round': rnd,
            'cost': round_result['total_cost'],
            'product_details': round_result['product_details'],
        })
        total_cost += round_result['total_cost']

    return {
        'total_cost': total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'round_costs': round_costs,
    }


def calculate_suggested_price(material_cost, markup_pct, base_fee=Decimal('0')):
    """Calculate suggested price from material cost + markup + base fee.

    Formula: material_cost x (1 + markup_pct/100) + base_fee

    Args:
        material_cost: Decimal total material cost
        markup_pct: Decimal markup percentage (e.g., 40 for 40%)
        base_fee: Decimal per-visit base/stop fee

    Returns:
        Decimal: suggested price, rounded to 2 decimal places
    """
    cost = Decimal(str(material_cost))
    markup = Decimal(str(markup_pct))
    fee = Decimal(str(base_fee))

    multiplier = Decimal('1') + markup / Decimal('100')
    price = cost * multiplier + fee
    return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_enrollment_pricing(program, square_feet, markup_pct, base_fee=Decimal('0')):
    """Calculate full enrollment pricing breakdown.

    This is the main function called during enrollment. Returns everything
    needed to show the auto-pricing preview to the business owner.

    Args:
        program: FertilizationProgram instance
        square_feet: property lawn area (int)
        markup_pct: Decimal markup percentage
        base_fee: Decimal per-visit base fee

    Returns:
        dict with:
            - total_material_cost: Decimal
            - num_rounds: int
            - cost_per_round: Decimal (average)
            - suggested_per_application: Decimal
            - suggested_annual: Decimal
            - round_breakdown: list of dicts per round with
                round, material_cost, suggested_price, product_details
    """
    markup = Decimal(str(markup_pct))
    fee = Decimal(str(base_fee))

    program_costs = calculate_program_material_cost(program, square_feet)
    total_material = program_costs['total_cost']
    num_rounds = len(program_costs['round_costs'])

    # Handle zero-rounds edge case
    if num_rounds == 0:
        return {
            'total_material_cost': Decimal('0.00'),
            'num_rounds': 0,
            'cost_per_round': Decimal('0.00'),
            'suggested_per_application': Decimal('0.00'),
            'suggested_annual': Decimal('0.00'),
            'round_breakdown': [],
        }

    cost_per_round = (total_material / Decimal(str(num_rounds))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    # Build per-round breakdown with suggested prices
    round_breakdown = []
    suggested_annual = Decimal('0')

    for rc in program_costs['round_costs']:
        suggested = calculate_suggested_price(rc['cost'], markup, fee)
        round_breakdown.append({
            'round': rc['round'],
            'material_cost': rc['cost'],
            'suggested_price': suggested,
            'product_details': rc['product_details'],
        })
        suggested_annual += suggested

    suggested_annual = suggested_annual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Average suggested price per application
    suggested_per_application = (suggested_annual / Decimal(str(num_rounds))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    return {
        'total_material_cost': total_material,
        'num_rounds': num_rounds,
        'cost_per_round': cost_per_round,
        'suggested_per_application': suggested_per_application,
        'suggested_annual': suggested_annual,
        'round_breakdown': round_breakdown,
    }
