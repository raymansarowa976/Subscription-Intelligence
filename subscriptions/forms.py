from django import forms

from .models import Subscription


class ManualSubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ["merchant_name", "amount", "currency", "cadence", "category", "next_renewal"]
        widgets = {
            "merchant_name": forms.TextInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition focus:border-pine focus:ring-4 focus:ring-pine/10",
                    "placeholder": "Example: Netflix",
                }
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition focus:border-pine focus:ring-4 focus:ring-pine/10",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "currency": forms.TextInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm uppercase text-ink shadow-sm outline-none transition focus:border-pine focus:ring-4 focus:ring-pine/10",
                    "placeholder": "USD",
                }
            ),
            "cadence": forms.Select(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition focus:border-pine focus:ring-4 focus:ring-pine/10",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition focus:border-pine focus:ring-4 focus:ring-pine/10",
                }
            ),
            "next_renewal": forms.DateInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition focus:border-pine focus:ring-4 focus:ring-pine/10",
                    "type": "date",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].initial = "USD"
        self.fields["cadence"].choices = [
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ]

    def clean_currency(self):
        return self.cleaned_data["currency"].upper()
