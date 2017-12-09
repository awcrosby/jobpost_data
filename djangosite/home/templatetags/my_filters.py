from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@stringfilter
def rel_font(value, max_font):
    """Returns relative font size based on max_font"""
    font_size = int(int(value)/int(max_font) * 100)
    return str(font_size)
register.filter('rel_font', rel_font, is_safe=True)
