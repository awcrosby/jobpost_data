from django import forms
from .models import QueryLoc, ScraperParams

LOCATION_CHOICES = (
    ('raleigh, nc','Raleigh, NC'),
    ('baltimore, md', 'Baltimore, MD'),
    # ('washington, dc','Washington, DC'),
    # ('new york, ny','New York, NY'),
)

class UserQueryForm(forms.Form):
    query = forms.CharField(label='Query', max_length=100)
    test = forms.ModelChoiceField(queryset=QueryLoc.objects.all().order_by('name'))
    location = forms.CharField(label='Location',
        widget=forms.Select(choices=LOCATION_CHOICES))

class ScraperForm(forms.Form):
    params = forms.ModelChoiceField(queryset=ScraperParams.objects.all(),
                                    widget=forms.RadioSelect,
                                    empty_label=None,
                                    label='')

class SkillsForm(forms.Form):
    widgets = {'any_field': forms.HiddenInput(),}
