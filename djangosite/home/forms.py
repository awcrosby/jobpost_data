from django import forms

LOCATION_CHOICES = (
    ('raleigh, nc','Raleigh, NC'),
    ('baltimore, md', 'Baltimore, MD'),
    # ('washington, dc','Washington, DC'),
    # ('new york, ny','New York, NY'),
)

class NameForm(forms.Form):
    query = forms.CharField(label='Query', max_length=100)
    location = forms.CharField(label='Location',
        widget=forms.Select(choices=LOCATION_CHOICES))
