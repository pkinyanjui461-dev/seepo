from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """Split a string by a delimiter. Usage: {{ "a,b,c"|split:"," }}"""
    return value.split(delimiter)

@register.filter
def chunks(value, chunk_size):
    """Split a list into chunks of size n."""
    if not value:
        return []
    try:
        chunk_size = int(chunk_size)
    except (ValueError, TypeError):
        return [value]
    return [value[i:i + chunk_size] for i in range(0, len(value), chunk_size)]

@register.filter
def get_item(dictionary, key):
    """Look up a key in a dict from a template. Usage: {{ my_dict|get_item:key }}"""
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
