"""Cálculo monetario único; las liquidaciones cerradas conservan su instantánea."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')


def amounts(order):
    labor = order.labor_cost if order.labor_cost is not None else order.base_total
    parts = order.parts_cost or Decimal('0.00')
    rate = order.tax_rate if order.tax_rate is not None else Decimal('0.00')
    if order.status != 'delivered':
        parts += sum((option.price for quote in order.quotes if quote.decision == 'approved'
                      for option in quote.options if option.id == quote.selected_option_id), Decimal('0.00'))
    subtotal = labor + parts
    tax = (subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    total = subtotal + tax
    if order.status == 'delivered' and order.total_amount is not None:
        tax, total = order.tax_amount, order.total_amount
    return labor, parts, subtotal, rate, tax, total


def freeze_final(order):
    labor, parts, _, rate, tax, total = amounts(order)
    order.labor_cost, order.parts_cost, order.tax_rate = labor, parts, rate
    order.tax_amount, order.total_amount = tax, total
