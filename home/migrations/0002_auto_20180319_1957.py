# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-03-19 19:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='weatherbymonth',
            name='weather_str',
            field=models.TextField(),
        ),
    ]
