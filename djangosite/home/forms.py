from django import forms
from .models import QueryLoc, ScraperParams

class UserQueryForm(forms.Form):
    query = forms.CharField(label='', max_length=30)

class ScraperForm(forms.Form):
    params = forms.ModelChoiceField(queryset=ScraperParams.objects.all().order_by('id'),
                                    widget=forms.RadioSelect,
                                    empty_label=None,
                                    label='')

class SkillsForm(forms.Form):
    widgets = {'any_field': forms.HiddenInput(),}
