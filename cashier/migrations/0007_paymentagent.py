from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0006_alter_deposit_method'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentAgent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('phone_number', models.CharField(help_text='Shown to users exactly as entered, e.g. 0712345678', max_length=20)),
                ('is_active', models.BooleanField(default=True, help_text='Uncheck to hide from the app without deleting the record')),
                ('display_order', models.PositiveIntegerField(default=0, help_text='Lower numbers appear first in the list')),
            ],
            options={
                'ordering': ['display_order', 'name'],
            },
        ),
    ]