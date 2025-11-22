from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(value, key):
    """Return dictionary value for key. Works with dict and objects that support .get()."""
    try:
        # Prefer dictionary-like access
        if hasattr(value, 'get'):
            return value.get(key)
        # Fallback to index/key access
        return value[key]
    except Exception:
        return None
