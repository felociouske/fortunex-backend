from django import forms


class RemarkForm(forms.Form):
    """
    Intermediate form shown after selecting deposits/withdrawals and
    choosing Approve/Reject from the admin actions dropdown. Lets the
    admin attach an optional remark, which becomes part of the
    notification message sent to the user.
    """
    remark = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Optional. Shown to the user as part of their notification.",
    )