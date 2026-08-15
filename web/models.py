import uuid

from django.db import models
from django.utils import timezone


class ScenarioModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, default="New Scenario")
    purpose = models.CharField(
        max_length=20,
        choices=[("purchase", "Purchase"), ("refinance", "Refinance")],
        default="purchase",
    )
    property_value = models.DecimalField(max_digits=12, decimal_places=2)
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    down_payment = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    fico_band = models.CharField(
        max_length=20,
        choices=[
            ("760+", "760+"),
            ("740-759", "740-759"),
            ("720-739", "720-739"),
            ("700-719", "700-719"),
            ("680-699", "680-699"),
            ("660-679", "660-679"),
            ("640-659", "640-659"),
            ("620-639", "620-639"),
            ("580-619", "580-619"),
            ("<580", "<580"),
        ],
        default="760+",
        null=True,
        blank=True,
    )
    occupancy = models.CharField(
        max_length=20,
        choices=[
            ("primary", "Primary Residence"),
            ("second_home", "Second Home"),
            ("investment", "Investment Property"),
        ],
        default="primary",
    )
    property_type = models.CharField(
        max_length=20,
        choices=[
            ("single_family", "Single Family"),
            ("condo", "Condo"),
            ("townhome", "Townhome"),
            ("multi_unit", "Multi-Unit (2-4)"),
        ],
        default="single_family",
    )
    state = models.CharField(max_length=2, default="CA")
    county_fips = models.CharField(max_length=10, null=True, blank=True)
    program = models.CharField(
        max_length=20,
        choices=[
            ("conventional", "Conventional"),
            ("fha", "FHA"),
            ("va", "VA"),
            ("usda", "USDA"),
        ],
        default="conventional",
    )
    term_months = models.PositiveIntegerField(default=360)
    expected_horizon_months = models.PositiveIntegerField(default=84)  # 7 years
    gross_monthly_income = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    recurring_monthly_debts = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    estimated_property_tax_monthly = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    estimated_homeowners_insurance_monthly = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    estimated_hoa_monthly = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scenario"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} (${self.loan_amount:,.0f})"


class LoanOptionModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(
        ScenarioModel,
        on_delete=models.CASCADE,
        related_name="loan_options",
    )
    label = models.CharField(max_length=255)
    source_type = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual Entry"),
            ("loan_estimate", "Transcribed Loan Estimate"),
        ],
        default="manual",
    )
    entered_on = models.DateField(default=timezone.now)
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    note_rate = models.DecimalField(
        max_digits=8, decimal_places=6
    )  # e.g. 0.058750 for 5.875%
    apr = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    term_months = models.PositiveIntegerField(default=360)
    points_pct = models.DecimalField(
        max_digits=8, decimal_places=6, default=0
    )  # e.g. 0.020000 for 2%
    lender_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lender_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_mi = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    upfront_mi = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "loan_option"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.label} ({self.note_rate * 100:.3f}%)"


class BenchmarkPointModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    series = models.CharField(max_length=50)  # e.g. 'MORTGAGE30US', 'MORTGAGE15US'
    observed_on = models.DateField()
    value = models.DecimalField(max_digits=6, decimal_places=3)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "benchmark_point"
        unique_together = [("series", "observed_on")]
        ordering = ["-observed_on"]

    def __str__(self):
        return f"{self.series} on {self.observed_on}: {self.value}%"
