from django import template

register = template.Library()

@register.filter(name='dict_key')
def dict_key(d, key):
    if not isinstance(d, dict):
        return None
    return d.get(key)

@register.filter(name='safe_file_url')
def safe_file_url(field):
    if not field:
        return ''
    try:
        return field.url
    except Exception:
        return ''

