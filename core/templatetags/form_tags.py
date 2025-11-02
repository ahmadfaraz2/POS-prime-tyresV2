from django import template

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
