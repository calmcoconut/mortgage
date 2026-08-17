from decimal import Decimal, InvalidOperation

from django import forms

from web.models import LoanOptionModel, ScenarioModel


class CurrencyDecimalField(forms.DecimalField):
    """Custom DecimalField accepting formatted currency strings like '$650,000' or '650,000.00'."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, str):
            value = value.strip().replace("$", "").replace(",", "")
        return super().to_python(value)


def format_currency_initial(val):
    if val is None or val == "":
        return None
    try:
        dec = Decimal(str(val))
        if dec == dec.to_integral():
            return f"${int(dec):,}"
        return f"${dec:,.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return str(val)


class ScenarioForm(forms.ModelForm):
    property_value = CurrencyDecimalField(
        label="Home Price / Property Value ($)",
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$850,000",
                "inputmode": "numeric",
            }
        ),
    )
    loan_amount = CurrencyDecimalField(
        label="Loan Amount ($)",
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$680,000",
                "inputmode": "numeric",
            }
        ),
    )
    down_payment = CurrencyDecimalField(
        label="Down Payment ($)",
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$170,000",
                "inputmode": "numeric",
            }
        ),
    )
    gross_monthly_income = CurrencyDecimalField(
        label="Gross Monthly Income ($)",
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$15,000",
                "inputmode": "numeric",
            }
        ),
    )
    recurring_monthly_debts = CurrencyDecimalField(
        label="Recurring Monthly Debts ($)",
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$1,000",
                "inputmode": "numeric",
            }
        ),
    )
    estimated_property_tax_monthly = CurrencyDecimalField(
        label="Estimated Property Tax ($/mo)",
        max_digits=8,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$850",
                "inputmode": "numeric",
            }
        ),
    )
    estimated_homeowners_insurance_monthly = CurrencyDecimalField(
        label="Estimated Homeowners Insurance ($/mo)",
        max_digits=8,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$140",
                "inputmode": "numeric",
            }
        ),
    )
    estimated_hoa_monthly = CurrencyDecimalField(
        label="Estimated HOA Monthly ($/mo)",
        max_digits=8,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$0",
                "inputmode": "numeric",
            }
        ),
    )
    annual_appreciation_pct = forms.DecimalField(
        label="Annual Home Price Appreciation (%)",
        max_digits=8,
        decimal_places=4,
        required=False,
        initial=Decimal("3.0"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-input",
                "placeholder": "3.0",
                "step": "0.1",
            }
        ),
        help_text="Expected annual home value appreciation rate (default: 3.0%).",
    )
    marginal_tax_rate_pct = forms.DecimalField(
        label="Marginal Income Tax Bracket (%)",
        max_digits=8,
        decimal_places=4,
        required=False,
        initial=Decimal("24.0"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-input",
                "placeholder": "24.0",
                "step": "0.5",
            }
        ),
        help_text="Combined federal and state marginal tax rate (e.g. 24% Fed + 9.3% CA = 33.3%).",
    )
    itemize_deductions = forms.BooleanField(
        label="Itemize Tax Deductions",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        help_text="Check if you itemize deductions (interest deductible up to $750k acquisition debt).",
    )

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
            "annual_appreciation_pct",
            "marginal_tax_rate_pct",
            "itemize_deductions",
            "filing_status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Mountain View Purchase",
                }
            ),
            "purpose": forms.Select(attrs={"class": "form-select"}),
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
            "filing_status": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_annual_appreciation_pct(self):
        val = self.cleaned_data.get("annual_appreciation_pct")
        if val is None:
            return Decimal("0.0300")
        if val > Decimal("1.0"):
            return (val / Decimal("100")).quantize(Decimal("0.0001"))
        return val.quantize(Decimal("0.0001"))

    def clean_marginal_tax_rate_pct(self):
        val = self.cleaned_data.get("marginal_tax_rate_pct")
        if val is None:
            return Decimal("0.2400")
        if val > Decimal("1.0"):
            return (val / Decimal("100")).quantize(Decimal("0.0001"))
        return val.quantize(Decimal("0.0001"))

    def clean_filing_status(self):
        val = self.cleaned_data.get("filing_status")
        return val or "single"

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
            self.initial["annual_appreciation_pct"] = Decimal("3.0")
            self.initial["marginal_tax_rate_pct"] = Decimal("24.0")
            self.fields["annual_appreciation_pct"].initial = Decimal("3.0")
            self.fields["marginal_tax_rate_pct"].initial = Decimal("24.0")
            self.fields["filing_status"].initial = "single"
            self.fields["filing_status"].required = False
        else:
            if self.instance.annual_appreciation_pct is not None:
                pct_val = round(
                    self.instance.annual_appreciation_pct * Decimal("100"), 2
                )
                self.initial["annual_appreciation_pct"] = pct_val
                self.fields["annual_appreciation_pct"].initial = pct_val
            if self.instance.marginal_tax_rate_pct is not None:
                tax_val = round(
                    self.instance.marginal_tax_rate_pct * Decimal("100"), 2
                )
                self.initial["marginal_tax_rate_pct"] = tax_val
                self.fields["marginal_tax_rate_pct"].initial = tax_val
            for field_name in [
                "property_value",
                "loan_amount",
                "down_payment",
                "gross_monthly_income",
                "recurring_monthly_debts",
                "estimated_property_tax_monthly",
                "estimated_homeowners_insurance_monthly",
                "estimated_hoa_monthly",
            ]:
                val = getattr(self.instance, field_name, None)
                if val is not None:
                    formatted = format_currency_initial(val)
                    if formatted is not None:
                        self.initial[field_name] = formatted


class LoanOptionForm(forms.ModelForm):
    loan_amount = CurrencyDecimalField(
        label="Loan Amount ($)",
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$500,000",
                "inputmode": "numeric",
            }
        ),
    )
    lender_credit = CurrencyDecimalField(
        label="Lender Credits ($)",
        max_digits=10,
        decimal_places=2,
        required=False,
        initial=Decimal("0.0"),
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$0",
                "inputmode": "numeric",
            }
        ),
    )
    lender_fees = CurrencyDecimalField(
        label="Lender Fees ($)",
        max_digits=10,
        decimal_places=2,
        required=False,
        initial=Decimal("0.0"),
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$0",
                "inputmode": "numeric",
            }
        ),
    )
    monthly_mi = CurrencyDecimalField(
        label="Monthly MI ($/mo)",
        max_digits=8,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$0",
                "inputmode": "numeric",
            }
        ),
    )
    upfront_mi = CurrencyDecimalField(
        label="Upfront MI ($) (FHA/USDA)",
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input currency-input",
                "placeholder": "$0",
                "inputmode": "numeric",
            }
        ),
    )
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
        widgets = {
            "label": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. 30Y Fixed (Option A)",
                }
            ),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "entered_on": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "term_months": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "360"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                    "placeholder": "Optional transcription notes, lender name, or locked rate details",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.note_rate is not None:
                rate_val = (self.instance.note_rate * Decimal("100")).normalize()
                self.fields["rate_percent"].initial = rate_val
                self.initial["rate_percent"] = rate_val
            if self.instance.apr is not None:
                apr_val = (self.instance.apr * Decimal("100")).normalize()
                self.fields["apr_percent"].initial = apr_val
                self.initial["apr_percent"] = apr_val
            if self.instance.points_pct is not None:
                pts_val = (self.instance.points_pct * Decimal("100")).normalize()
                self.fields["points_percent"].initial = pts_val
                self.initial["points_percent"] = pts_val
            for field_name in [
                "loan_amount",
                "lender_credit",
                "lender_fees",
                "monthly_mi",
                "upfront_mi",
            ]:
                val = getattr(self.instance, field_name, None)
                if val is not None:
                    formatted = format_currency_initial(val)
                    if formatted is not None:
                        self.initial[field_name] = formatted

        # Also format any passed initial dict
        if "initial" in kwargs and kwargs["initial"]:
            for field_name in [
                "loan_amount",
                "lender_credit",
                "lender_fees",
                "monthly_mi",
                "upfront_mi",
            ]:
                if field_name in self.initial and self.initial[field_name] is not None:
                    formatted = format_currency_initial(self.initial[field_name])
                    if formatted is not None:
                        self.initial[field_name] = formatted

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
