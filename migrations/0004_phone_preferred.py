# Generated by Django 2.2.17 on 2020-12-19 15:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mjg_base', '0003_auto_20201219_1102'),
    ]

    operations = [
        migrations.AddField(
            model_name='phone',
            name='preferred',
            field=models.CharField(default='N', max_length=1),
        ),
    ]
