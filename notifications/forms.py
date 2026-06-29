"""
Custom admin form for creating promotional/system notifications,
letting an admin target either one specific user or broadcast to
everyone -- this can't be a normal ModelAdmin add form since "target"
isn't a real field on Notification (a broadcast creates one row per
user, not one row with a "to everyone" flag).
"""
from django import forms
from django.contrib.auth import get_user_model

from .models import Notification

User = get_user_model()


class SendNotificationForm(forms.Form):
    category = forms.ChoiceField(
        choices=[
            (Notification.CATEGORY_PROMOTIONAL, "Promotional"),
            (Notification.CATEGORY_SYSTEM, "System"),
        ]
    )
    target = forms.ChoiceField(
        choices=[("all", "All users"), ("one", "Specific user")],
        widget=forms.RadioSelect,
        initial="all",
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.all(), required=False,
        help_text="Required only when targeting a specific user.",
    )
    title = forms.CharField(max_length=150)
    message = forms.CharField(widget=forms.Textarea)
    action_url = forms.CharField(max_length=255, required=False, help_text="Optional, e.g. /bots")
    action_label = forms.CharField(max_length=50, required=False, help_text="Optional, e.g. \"View offer\"")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("target") == "one" and not cleaned.get("user"):
            raise forms.ValidationError("Select a user when targeting a specific user.")
        return cleaned