from django.contrib import admin
from .models import BotProduct


@admin.register(BotProduct)
class BotProductAdmin(admin.ModelAdmin):
    search_fields = ["name", "category"]
    list_display = ["name", "category", "price", "active"]
    list_filter = ["active", "category"]
