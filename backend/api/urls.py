from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("upload/", views.upload_file, name="upload"),
    path("pattern/generate/", views.generate_pattern, name="pattern-generate"),
    path("transform/apply/", views.apply_transform, name="transform-apply"),
    path("download/<str:export_id>/", views.download_export, name="download-export"),
]
