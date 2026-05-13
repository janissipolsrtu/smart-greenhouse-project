from django import forms
from django.contrib.auth.models import User


class RegistrationForm(forms.Form):
    email = forms.EmailField(label='E-pasts', max_length=254)
    password1 = forms.CharField(label='Parole', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Parole atkārtoti', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Lietotājs ar šo e-pastu jau eksistē.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Paroles nesakrīt.')

        return cleaned_data
