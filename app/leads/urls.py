from django.urls import path
from . import views

app_name = "leads"

urlpatterns = [
    path("", views.LeadListView.as_view(), name="list"),
    path("add/", views.LeadCreateView.as_view(), name="create"),
    path("<int:pk>/", views.LeadDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.LeadUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.LeadDeleteView.as_view(), name="delete"),
    path("import/", views.import_csv_view, name="import"),
    path("export/", views.export_csv_view, name="export"),
    path("lists/", views.LeadListListView.as_view(), name="lead-lists"),
    path("lists/add/", views.LeadListCreateView.as_view(), name="lead-list-create"),
]
