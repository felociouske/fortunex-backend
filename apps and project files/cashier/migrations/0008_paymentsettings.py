from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0007_paymentagent'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paybill_number', models.CharField(default='174379', max_length=20)),
                ('account_name', models.CharField(default='FortuneX', help_text='Shown as the Account Number step in payment instructions, a shared brand name, not a per-user reference', max_length=50)),
            ],
        ),
    ]