# Generated by Django 2.2.17 on 2021-01-01 16:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mjg_base', '0005_feature'),
    ]

    operations = [
        migrations.AlterField(
            model_name='feature',
            name='group_code',
            field=models.CharField(blank=True, default=None, help_text='Group features to toggle an entire set of features together', max_length=80, null=True, verbose_name='Group Code'),
        ),
    ]