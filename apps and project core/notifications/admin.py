from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages as django_messages

from .models import Notification
from .forms import SendNotificationForm
from .services import notify_broadcast


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "title"]
    list_display = ["user", "category", "title", "read", "created_at"]
    list_filter = ["category", "read"]
    change_list_template = "admin/notifications/notification/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("send/", self.admin_site.admin_view(self.send_notification_view), name="notifications_send"),
        ]
        return custom + urls

    def send_notification_view(self, request):
        """
        Custom admin page (linked from the change-list's 'Send notification'
        button) letting an admin broadcast a promotional/system notification
        to everyone, or target one specific user.
        """
        if request.method == "POST":
            form = SendNotificationForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                users = None if data["target"] == "all" else [data["user"]]
                created = notify_broadcast(
                    category=data["category"],
                    title=data["title"],
                    message=data["message"],
                    users=users,
                    action_url=data.get("action_url", ""),
                    action_label=data.get("action_label", ""),
                )
                django_messages.success(request, f"Sent notification to {len(created)} user(s).")
                return redirect("admin:notifications_notification_changelist")
        else:
            form = SendNotificationForm()

        return render(request, "admin/notifications/notification/send_form.html", {
            "form": form,
            "title": "Send notification",
            "opts": self.model._meta,
        })