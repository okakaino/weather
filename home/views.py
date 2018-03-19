# -*- coding: utf-8 -*-

import json
import re

from datetime import datetime
from dateutil import relativedelta, rrule
from random import choice
from urllib.parse import quote

import MySQLdb
import requests
import pytz

from django.views import View
from django.http import HttpResponse
from django.shortcuts import render
from excel_response.response import ExcelResponse

from .logger import logger
from .models import WeatherByMonth
from .user_agents import user_agents


def index(request):
    if request.method == 'POST':
        logger.debug('got POST request from {}'.format(get_client_ip(request)))
        city = request.POST.get('city', '')
        start_date_str = request.POST.get('start_date', '')
        end_date_str = request.POST.get('end_date', '')
        logger.debug('city: {}, start date: {}, end date: {}'.format(
            city, start_date_str, end_date_str))
        
        msg = ''
        
        if city and start_date_str and end_date_str:
            city_code = city.split('|')[0]
            city_name = city.split('|')[1].split()[-1]
            get_dates_re = re.compile(r'\d+')
            start_dates = get_dates_re.findall(start_date_str)
            end_dates = get_dates_re.findall(end_date_str)
            
            start_date = validate_start_date(start_dates)
            end_date = validate_end_date(end_dates)
            logger.debug('parsed dates: {} - {}'.format(start_date, end_date))

            if start_date > end_date:
                start_date, end_date = end_date, start_date

            delta_m = relativedelta.relativedelta(end_date, start_date)
            logger.debug('{} month(s) date difference'.format(delta_m.months))

            weather_lst = []

            for dt in rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date):
                year = dt.year
                month = dt.month

                date_str = str(year) + '-' + str(month)
                weather_query = WeatherByMonth.objects.filter(month=date_str, city_code=city_code)

                if weather_query.exists():
                    logger.debug('weather data for {} of {} found in database'.format(city_name, date_str))
                    weather_str = weather_query.first().weather_str
                else:
                    logger.debug('weather data for {} of {} not in database'.format(city_name, date_str))
                    weather_str = fetch_html(city=city_code, year=year, month=month)
                    logger.debug('got http response javascript, saving to database')
                    new_weather, created = WeatherByMonth.objects.get_or_create(city_code=city_code, month=date_str)
                    new_weather.weather_str = weather_str
                    new_weather.save()

                month_weather_data = parse_weather(weather_str)
                logger.debug('parsing data from string {}'.format('succeeded' if month_weather_data else 'failed'))
                while not month_weather_data:
                    logger.debug('retrying downloading html')
                    weather_str = fetch_html(city=city_code, year=year, month=month)
                    logger.debug('got http response javascript, saving to database')
                    new_weather, created = WeatherByMonth.objects.get_or_create(city_code=city_code, month=date_str)
                    new_weather.city_name = city_name
                    new_weather.weather_str = weather_str
                    new_weather.save()

                    month_weather_data = parse_weather(weather_str)
                    logger.debug('parsing data from string {}'.format('succeeded' if month_weather_data else 'failed'))

                weather_lst += month_weather_data

            weather_data = [['日期', '最高溫度', '最低溫度', '天氣', '風向', '風力', 'AQI', 'AQI水平']]
            header_names = ['ymd', 'bWendu', 'yWendu', 'tianqi', 'fengxiang', 'fengli', 'aqi', 'aqiInfo']
            for weather in weather_lst:
                try:
                    d = datetime.strptime(weather.get(header_names[0], ''), '%Y-%m-%d')
                    logger.debug('got date from weather dict: {}'.format(d))
                    if start_date <= d <= end_date:
                        weather_data.append(dict2list(weather, header_names))
                except Exception as e:
                    logger.debug('failed to get date from weather dict, {}'.format(e))
                    pass
            logger.debug('got data for {} days'.format(len(weather_data)))

            filename = quote('{}{}-{}天氣'.format(city_name, start_date_str, end_date_str))
            filename_extra = "; filename*=utf-8''{}".format(filename)
            filename += filename_extra
            logger.debug('generating excel file {}'.format(filename))
                        
            return ExcelResponse(weather_data, output_filename=filename)
        else:
            msg = '信息不全'
        
        context = {
            'message': msg,
        }

        return render(request, 'index.html', context=context)
    else:
        return render(request, 'index.html')

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[-1].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def validate_date(date, min_default=False):
    min_date = datetime(2016, 3, 1)
    today = datetime.now()

    try:
        date = [int(i) for i in date]
        date_to_compare = datetime(*date)
    except:
        if min_default:
            return min_date
        else:
            return today
    else:
        if date_to_compare < min_date:
            return min_date
        elif date_to_compare > today:
            return today
        else:
            return date_to_compare

def validate_start_date(date):
    return validate_date(date, min_default=True)

def validate_end_date(date):
    return validate_date(date)

def get_proxy():
    proxy_pool_url = 'http://localhost:5555/random'
    response = requests.get(proxy_pool_url)
    proxy = response.text.strip()
    http_proxy = "http://" + proxy
    return http_proxy

def fetch_html(city, year, month):
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Referer': 'http://tianqi.2345.com/wea_history/{}.htm'.format(city),
        'User-Agent': choice(user_agents),
    }

    # http://tianqi.2345.com/t/wea_history/js/54511_20153.js
    url = 'http://tianqi.2345.com/t/wea_history/js/{year:04d}{month:02d}/{city}_{year:04d}{month:02d}.js'.format(
        year=year, city=city, month=month
    )
    logger.debug('fetching {}'.format(url))

    # http_proxy = get_proxy()
    # logger.debug('using proxy: {}'.format(http_proxy))
    # proxies = {
    #     "http" : http_proxy,
    # }

    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            logger.debug('html downloaded for {} of {}-{}'.format(city, year, month))
            return r.text
        else:
            logger.debug('http response {}, retrying'.format(r.status_code))
            return fetch_html(city, year, month)
    except Exception as e:
        logger.debug('failed to send http request, {}, retrying'.format(e))
        return fetch_html(city, year, month)

def parse_weather(response):
    try:
        a = re.findall('weather_str=(.*);\s*', response, re.S)[0]
        b = re.findall(r'tqInfo:\[(.*)\]', a)[0]
        c = re.findall(r'\{(.*?)\}', b)
        c = [i for i in c if i]
        weather_lst = []
        for i in c:
            d = re.sub(r'([a-zA-Z]+)', r'"\1"', i)
            e = re.sub(r'^(.*)$', r'{\1}', d)
            f = re.sub(r'\'', r'"', e)
            weather_lst.append(json.loads(f))
        logger.debug('got weather data, length of {}'.format(len(weather_lst)))
        return weather_lst
    except Exception as e:
        logger.debug('failed to parse weather data, {}'.format(e))
        return []

def dict2list(dict_to_convert, keys, default=''):
    result = []
    for key in keys:
        result.append(dict_to_convert.get(key, default))
    
    return result