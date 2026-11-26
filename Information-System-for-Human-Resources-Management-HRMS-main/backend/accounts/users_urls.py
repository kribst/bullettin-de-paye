from django.urls import path

from . import views

urlpatterns = [
    path("users/", views.UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("users/<int:pk>/deactivate/", views.UserDeactivateView.as_view(), name="user-deactivate"),
    path("users/<int:pk>/activate/", views.UserActivateView.as_view(), name="user-activate"),
    path("users/<int:pk>/reset-password/", views.UserResetPasswordView.as_view(), name="user-reset-password"),
]
