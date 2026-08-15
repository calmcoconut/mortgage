from django.urls import path

from web import views

app_name = "web"

urlpatterns = [
    path("", views.scenario_list, name="scenario_list"),
    path("scenarios/new/", views.scenario_create, name="scenario_create"),
    path(
        "scenarios/<uuid:scenario_id>/edit/", views.scenario_edit, name="scenario_edit"
    ),
    path(
        "scenarios/<uuid:scenario_id>/delete/",
        views.scenario_delete,
        name="scenario_delete",
    ),
    path(
        "scenarios/<uuid:scenario_id>/compare/",
        views.scenario_compare,
        name="scenario_compare",
    ),
    path(
        "scenarios/<uuid:scenario_id>/projected-costs/",
        views.scenario_projected_costs,
        name="scenario_projected_costs",
    ),
    path(
        "scenarios/<uuid:scenario_id>/options/new/",
        views.option_create,
        name="option_create",
    ),
    path(
        "scenarios/<uuid:scenario_id>/options/<uuid:option_id>/edit/",
        views.option_edit,
        name="option_edit",
    ),
    path(
        "scenarios/<uuid:scenario_id>/options/<uuid:option_id>/delete/",
        views.option_delete,
        name="option_delete",
    ),
    path(
        "scenarios/screen-preview/",
        views.scenario_screen_preview,
        name="scenario_screen_preview",
    ),
    path(
        "scenarios/<uuid:scenario_id>/enrich-offers/",
        views.scenario_enrich_preview,
        name="scenario_enrich_preview",
    ),
    path(
        "scenarios/<uuid:scenario_id>/import-offer/",
        views.scenario_import_rateapi_offer,
        name="scenario_import_rateapi_offer",
    ),
    path("rate-watch/", views.rate_watch, name="rate_watch"),
    path("learn/", views.learn, name="learn"),
]

