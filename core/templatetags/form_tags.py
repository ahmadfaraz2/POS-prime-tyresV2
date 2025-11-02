from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from decimal import Decimal

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css):
    """Append css classes to a form field widget while preserving existing ones."""
    if hasattr(field, 'as_widget'):
        attrs = field.field.widget.attrs
        existing = attrs.get('class', '')
        new_classes = f"{existing} {css}".strip() if existing else css
        return field.as_widget(attrs={**attrs, 'class': new_classes})
    return field


@register.filter(name='currency')
def currency(value):
    """Format currency with commas and without decimals if they are .00, otherwise show 2 decimals."""
    try:
        # Convert to Decimal for precise comparison
        if isinstance(value, str):
            value = Decimal(value)
        elif not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Check if value is a whole number
        if value % 1 == 0:
            return intcomma(int(value))
        else:
            # Format with 2 decimals and add commas
            return intcomma(f"{value:.2f}")
    except (ValueError, TypeError, ArithmeticError):
        return value
