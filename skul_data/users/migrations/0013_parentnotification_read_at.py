# Generated by Django 5.1.7 on 2025-05-20 16:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_role_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='parentnotification',
            name='read_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
