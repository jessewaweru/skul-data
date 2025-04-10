# Generated by Django 5.1.7 on 2025-04-09 10:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_initial'),
        ('schools', '0003_school_code_school_level_school_superuser_profile_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_custom', models.BooleanField(default=False)),
                ('school', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='schools.school')),
            ],
        ),
        migrations.AlterField(
            model_name='document',
            name='category',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='documents.documentcategory'),
        ),
    ]
