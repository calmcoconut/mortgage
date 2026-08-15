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
            ("rate_api", "RateAPI Market Offer"),
        ],
        default="manual",
    )
    institution_name = models.CharField(max_length=255, blank=True, default="")
    confidence_score = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True
    )
    external_reference_id = models.CharField(max_length=255, blank=True, default="")
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


class RateApiCacheModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)
    query_state = models.CharField(max_length=10)
    query_intent = models.CharField(max_length=20)
    query_amount_bucket = models.PositiveIntegerField()
    query_term_months = models.PositiveIntegerField()
    response_payload = models.JSONField()
    cached_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "rate_api_cache"
        ordering = ["-cached_at"]

    def __str__(self):
        return f"Cache {self.cache_key} (expires {self.expires_at})"


class RateApiBudgetModel(models.Model):
    month_key = models.CharField(max_length=7, primary_key=True)  # 'YYYY-MM'
    call_count = models.PositiveIntegerField(default=0)
    monthly_limit = models.PositiveIntegerField(default=20)
    safety_threshold = models.PositiveIntegerField(default=18)
    last_called_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "rate_api_budget"

    def __str__(self):
        return f"Budget {self.month_key}: {self.call_count}/{self.monthly_limit} (Limit: {self.safety_threshold})"


class RateApiSnapshotModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    lender = models.CharField(max_length=255, db_index=True)
    state = models.CharField(max_length=10, default="CA", db_index=True)
    product_type = models.CharField(max_length=50, db_index=True)  # e.g. '30-year-fixed', '5-1-arm'
    product_name = models.CharField(max_length=255, blank=True, default="")
    loan_program = models.CharField(max_length=50, default="conventional")
    rate = models.DecimalField(max_digits=6, decimal_places=3)
    apr = models.DecimalField(max_digits=6, decimal_places=3)
    points = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    observed_on = models.DateField(default=timezone.now, db_index=True)
    fetched_at = models.DateTimeField(default=timezone.now)
    eligibility_summary = models.TextField(blank=True, default="")
    confidence_score = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)

    class Meta:
        db_table = "rate_api_snapshot"
        unique_together = [("lender", "product_type", "state", "observed_on")]
        ordering = ["-observed_on", "rate"]

    def __str__(self):
        return f"{self.lender} ({self.product_type}): {self.rate}% on {self.observed_on}"

