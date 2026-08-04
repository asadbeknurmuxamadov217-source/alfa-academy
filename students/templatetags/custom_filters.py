from django import template

register = template.Library()

@register.filter(name='dict_key')
def dict_key(d, key):
    if not isinstance(d, dict):
        return None
    return d.get(key)
