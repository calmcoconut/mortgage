from decimal import Decimal

from django import forms

from web.models import LoanOptionModel, ScenarioModel


class ScenarioForm(forms.ModelForm):
    class Meta:
        model = ScenarioModel
        fields = [
            "name",
            "purpose",
            "property_value",
            "loan_amount",
            "down_payment",
            "fico_band",
            "occupancy",
            "property_type",
            "state",
            "county_fips",
            "program",
            "term_months",
            "expected_horizon_months",
            "gross_monthly_income",
            "recurring_monthly_debts",
            "estimated_property_tax_monthly",
            "estimated_homeowners_insurance_monthly",
            "estimated_hoa_monthly",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Mountain View Purchase",
                }
            ),
            "purpose": forms.Select(attrs={"class": "form-select"}),
            "property_value": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "850000", "step": "1000"}
            ),
            "loan_amount": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "680000", "step": "1000"}
            ),
            "down_payment": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "170000", "step": "1000"}
            ),
            "fico_band": forms.Select(attrs={"class": "form-select"}),
            "occupancy": forms.Select(attrs={"class": "form-select"}),
            "property_type": forms.Select(attrs={"class": "form-select"}),
            "state": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "CA", "maxlength": "2"}
            ),
            "county_fips": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "06085"}
            ),
            "program": forms.Select(attrs={"class": "form-select"}),
            "term_months": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "360", "value": "360"}
            ),
            "expected_horizon_months": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "84", "value": "84"}
            ),
            "gross_monthly_income": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "15000", "step": "100"}
            ),
            "recurring_monthly_debts": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "1000", "step": "100"}
            ),
            "estimated_property_tax_monthly": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "850", "step": "10"}
            ),
            "estimated_homeowners_insurance_monthly": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "140", "step": "10"}
            ),
            "estimated_hoa_monthly": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "0", "step": "10"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["term_months"].initial = 360
            self.fields["expected_horizon_months"].initial = 84
            self.fields["state"].initial = "CA"
            self.fields["program"].initial = "conventional"
            self.fields["fico_band"].initial = "760+"
            self.fields["purpose"].initial = "purchase"
            self.fields["occupancy"].initial = "primary"
            self.fields["property_type"].initial = "single_family"
            self.initial.setdefault("property_type", "single_family")


class LoanOptionForm(forms.ModelForm):
    rate_percent = forms.DecimalField(
        label="Note Rate (%)",
        max_digits=10,
        decimal_places=4,
        widget=forms.NumberInput(
            attrs={"class": "form-input", "placeholder": "6.500", "step": "0.125"}
        ),
    )
    apr_percent = forms.DecimalField(
        label="APR (%)",
        max_digits=10,
        decimal_places=4,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-input", "placeholder": "6.500", "step": "0.001"}
        ),
    )
    points_percent = forms.DecimalField(
        label="Points (%)",
        max_digits=10,
        decimal_places=4,
        initial=Decimal("0.0"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "placeholder": "0.000", "step": "0.125"}
        ),
    )

    class Meta:
        model = LoanOptionModel
        fields = [
            "label",
            "source_type",
            "entered_on",
            "loan_amount",
            "term_months",
            "lender_credit",
            "lender_fees",
            "monthly_mi",
            "upfront_mi",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.note_rate is not None:
                self.fields["rate_percent"].initial = (
                    self.instance.note_rate * Decimal("100")
                ).normalize()
            if self.instance.apr is not None:
                self.fields["apr_percent"].initial = (
                    self.instance.apr * Decimal("100")
                ).normalize()
            if self.instance.points_pct is not None:
                self.fields["points_percent"].initial = (
                    self.instance.points_pct * Decimal("100")
                ).normalize()

    def clean(self):
        cleaned_data = super().clean()
        rate_p = cleaned_data.get("rate_percent")
        apr_p = cleaned_data.get("apr_percent")
        pts_p = cleaned_data.get("points_percent")

        if rate_p is not None:
            self.instance.note_rate = rate_p / Decimal("100")
        if apr_p is not None:
            self.instance.apr = apr_p / Decimal("100")
        else:
            self.instance.apr = None
        if pts_p is not None:
            self.instance.points_pct = pts_p / Decimal("100")
        return cleaned_data
