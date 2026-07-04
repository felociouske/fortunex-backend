import users.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_user_referral_code_alter_user_referred_by'),
    ]

    operations = [
        # ── Remove the old single-document KYC fields ────────────────────
        migrations.RemoveField(model_name='user', name='kyc_document'),
        migrations.RemoveField(model_name='user', name='kyc_submitted_at'),
        migrations.RemoveField(model_name='user', name='kyc_reviewed_at'),
        migrations.RemoveField(model_name='user', name='kyc_notes'),

        # ── New profile fields ────────────────────────────────────────────
        migrations.AddField(
            model_name='user',
            name='location',
            field=models.CharField(blank=True, help_text='e.g. Nairobi, Kenya', max_length=255),
        ),
        migrations.AddField(
            model_name='user',
            name='kra_pin',
            field=models.CharField(blank=True, help_text='Kenya Revenue Authority PIN, e.g. A123456789Z', max_length=11),
        ),

        # ── New per-category KYC model ────────────────────────────────────
        migrations.CreateModel(
            name='KYCSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('IDENTITY', 'Proof of Identity'), ('ADDRESS', 'Proof of Address'), ('OWNERSHIP', 'Proof of Ownership'), ('INCOME', 'Proof of Income')], max_length=12)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('SUBMITTED', 'Submitted'), ('VERIFIED', 'Verified'), ('REJECTED', 'Rejected')], default='PENDING', max_length=12)),
                ('document_type', models.CharField(blank=True, choices=[('NATIONAL_ID', 'National ID'), ('PASSPORT', 'Passport'), ('DRIVERS_LICENSE', "Driver's License")], max_length=20)),
                ('front_image', models.FileField(blank=True, null=True, upload_to=users.models.kyc_upload_path)),
                ('back_image', models.FileField(blank=True, null=True, upload_to=users.models.kyc_upload_path)),
                ('address_image', models.FileField(blank=True, null=True, upload_to=users.models.kyc_upload_path)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_notes', models.TextField(blank=True, help_text="Admin notes on this category's review")),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_submissions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='kycsubmission',
            constraint=models.UniqueConstraint(fields=('user', 'category'), name='one_submission_per_category'),
        ),
    ]
    