from django.urls import path
from . import views

app_name = "tracking"

urlpatterns = [
    path("open/<uuid:tracking_id>.png", views.track_open, name="open"),
    path("click/<uuid:tracking_id>/<path:encoded_url>/", views.track_click, name="click"),
    path("unsubscribe/<uuid:tracking_id>/", views.unsubscribe, name="unsubscribe"),
]
