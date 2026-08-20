from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.EventListView.as_view(), name="index"),
    path("tickets/", views.TicketListView.as_view(), name="list"),
    path("tickets/<int:pk>/", views.TicketDetailView.as_view(), name="detail"),
    path("tickets/<int:pk>/transfer/", views.TicketTransferView.as_view(), name="transfer"),
]
