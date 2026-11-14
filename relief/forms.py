from django import forms
NEED_CHOICES = [("housing","Housing / shelter"),("food","Food / water"),("financial","Financial assistance"),("transportation","Transportation"),("medical","Medical support"),("documents","Documents / recovery paperwork")]
CONSTRAINT_CHOICES = [("pet_friendly","Pet friendly"),("accessible","Accessible"),("no_car","No car / transportation needed"),("family","Family friendly")]
class ResourceFinderForm(forms.Form):
    location = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"placeholder":"Example: Asheville, NC","autocomplete":"off"}))
    need = forms.ChoiceField(choices=NEED_CHOICES)
    constraints = forms.MultipleChoiceField(choices=CONSTRAINT_CHOICES, required=False, widget=forms.CheckboxSelectMultiple)
