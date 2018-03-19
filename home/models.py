# -*- coding: utf-8 -*-

from django.db import models


class WeatherByMonth(models.Model):
    city_code = models.CharField(max_length=8)
    city_name = models.CharField(max_length=20)
    month = models.CharField(max_length=12)
    weather_str = models.TextField()

    def __str__(self):
        return self.city_name
    
    class Meta:
        unique_together = ('city_code', 'month',)