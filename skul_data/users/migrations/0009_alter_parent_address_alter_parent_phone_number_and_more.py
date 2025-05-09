# Generated by Django 5.1.7 on 2025-05-06 08:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_alter_parent_phone_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='parent',
            name='address',
            field=models.TextField(blank=True, max_length=300, null=True),
        ),
        migrations.AlterField(
            model_name='parent',
            name='phone_number',
            field=models.CharField(blank=True, max_length=21, null=True),
        ),
        migrations.AlterField(
            model_name='role',
            name='name',
            field=models.CharField(max_length=100),
        ),
    ]
