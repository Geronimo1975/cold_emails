from django.urls import path
from . import views

app_name = "sending"

urlpatterns = [
    path("accounts/", views.SmtpAccountListView.as_view(), name="account-list"),
    path("accounts/add/", views.SmtpAccountCreateView.as_view(), name="account-create"),
    path("accounts/<int:pk>/edit/", views.SmtpAccountUpdateView.as_view(), name="account-edit"),
    path("accounts/<int:pk>/delete/", views.SmtpAccountDeleteView.as_view(), name="account-delete"),
    path("accounts/<int:pk>/test/", views.test_smtp_connection, name="account-test"),
    path("logs/", views.EmailLogListView.as_view(), name="log-list"),
]
