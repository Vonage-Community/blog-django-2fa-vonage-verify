from django.contrib import admin

from .models import VerifiedPhone


@admin.register(VerifiedPhone)
class VerifiedPhoneAdmin(admin.ModelAdmin):
    list_display = ("user", "masked_number", "confirmed_at")
    readonly_fields = ("confirmed_at",)
