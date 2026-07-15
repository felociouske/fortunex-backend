from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0004_withdrawal_payout_details'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deposit',
            name='method',
            field=models.CharField(
                choices=[('MANUAL', 'Manual'), ('MPESA', 'M-Pesa (automatic)'), ('MANUAL_MPESA', 'M-Pesa (manual, user-submitted code)')],
                default='MANUAL', max_length=10,
            ),
        ),
    ]