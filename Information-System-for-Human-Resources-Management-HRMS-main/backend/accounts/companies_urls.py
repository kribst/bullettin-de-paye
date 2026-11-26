from django.urls import path

from . import views

urlpatterns = [
    path("companies/", views.CompanyListCreateView.as_view(), name="company-list-create"),
    path("companies/me/", views.CompanyMeView.as_view(), name="company-me"),
    path("companies/<int:pk>/", views.CompanyDetailView.as_view(), name="company-detail"),
    path("companies/<int:pk>/logo/", views.CompanyLogoView.as_view(), name="company-logo"),
    path("companies/<int:company_pk>/leaders/", views.CompanyLeaderListCreateView.as_view(), name="company-leader-list"),
    path(
        "companies/<int:company_pk>/leaders/<int:pk>/",
        views.CompanyLeaderDetailView.as_view(),
        name="company-leader-detail",
    ),
]
