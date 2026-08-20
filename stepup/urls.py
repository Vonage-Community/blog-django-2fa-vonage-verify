from django.urls import path

from . import views

app_name = "stepup"

urlpatterns = [
    path("", views.StartVerificationView.as_view(), name="start"),
    path("code/", views.CheckCodeView.as_view(), name="check"),
]
