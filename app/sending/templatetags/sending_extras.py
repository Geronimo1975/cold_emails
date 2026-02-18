from django import template

register = template.Library()


@register.filter
def dictlookup(dictionary, key):
    """Look up a key in a dictionary. Usage: {{ mydict|dictlookup:key }}"""
    if dictionary is None:
        return None
    return dictionary.get(key)
