from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0003_deposit_mpesa_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='withdrawal',
            name='payout_details',
            field=models.CharField(blank=True, help_text='Phone number, bank account, or other payout destination', max_length=255),
        ),
    ]