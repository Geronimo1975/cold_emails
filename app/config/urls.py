from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("campaigns.urls")),
    path("leads/", include("leads.urls")),
    path("sending/", include("sending.urls")),
    path("t/", include("tracking.urls")),
    path("api/", include("api.urls")),
]
