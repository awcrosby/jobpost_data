from django import forms
from .models import QueryLoc, ScraperParams

class UserQueryForm(forms.Form):
    query = forms.CharField(label='Query', max_length=100)
    location = forms.ModelChoiceField(queryset=QueryLoc.objects.all().order_by('name'))

class ScraperForm(forms.Form):
    params = forms.ModelChoiceField(queryset=ScraperParams.objects.all(),
                                    widget=forms.RadioSelect,
                                    empty_label=None,
                                    label='')

class SkillsForm(forms.Form):
    widgets = {'any_field': forms.HiddenInput(),}
