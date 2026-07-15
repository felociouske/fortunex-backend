# Adds the BluePay method choice (additive only -- does not touch any
# existing Daraja/M-Pesa method values or data). Chained after your
# existing 0007_paymentagent.py migration.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0007_paymentagent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deposit',
            name='method',
            field=models.CharField(
                choices=[
                    ('MANUAL', 'Manual'),
                    ('MPESA', 'M-Pesa (automatic)'),
                    ('MANUAL_MPESA', 'M-Pesa (manual, user-submitted code)'),
                    ('BLUEPAY', 'M-Pesa via BluePay'),
                ],
                default='MANUAL',
                max_length=20,
            ),
        ),
    ]