from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0002_deposit_reviewed_at_withdrawal_reviewed_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='deposit',
            name='method',
            field=models.CharField(choices=[('MANUAL', 'Manual'), ('MPESA', 'M-Pesa')], default='MANUAL', max_length=10),
        ),
        migrations.AddField(
            model_name='deposit',
            name='phone_number',
            field=models.CharField(blank=True, help_text='MSISDN in 2547XXXXXXXX format', max_length=15),
        ),
        migrations.AddField(
            model_name='deposit',
            name='kes_amount',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Actual KES amount sent to Daraja (amount * exchange_rate at request time)', max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name='deposit',
            name='exchange_rate',
            field=models.DecimalField(blank=True, decimal_places=4, help_text='USD->KES rate used at request time, kept for audit trail', max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='deposit',
            name='merchant_request_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='deposit',
            name='checkout_request_id',
            field=models.CharField(blank=True, default=None, max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='deposit',
            name='mpesa_receipt_number',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='deposit',
            name='result_code',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='deposit',
            name='result_desc',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='deposit',
            name='callback_received_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='deposit',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('FAILED', 'Failed')], default='PENDING', max_length=32),
        ),
    ]