from django.contrib import admin

from .models import Event, Ticket, Transfer


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("artist", "venue", "city", "starts_at")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("event", "owner", "section", "seat")
    list_filter = ("event",)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("ticket", "sender", "recipient", "created_at")
    readonly_fields = ("created_at",)
