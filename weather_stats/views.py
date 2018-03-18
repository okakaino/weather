# -*- coding: utf-8 -*-

import json
import re

from datetime import datetime
from dateutil import rrule
from random import choice
from urllib.parse import quote

import requests
import pytz

from django.views import View
from django.http import HttpResponse
from django.shortcuts import render
from excel_response.response import ExcelResponse

from .user_agents import user_agents


def index(request):
    if request.method == 'POST':
        city_code = request.POST.get('city', '')
        start_date_str = request.POST.get('start_date', '')
        end_date_str = request.POST.get('end_date', '')

        msg = ''
        
        if city_code and start_date_str and end_date_str:
            get_dates_re = re.compile(r'\d+')
            start_dates = get_dates_re.findall(start_date_str)
            end_dates = get_dates_re.findall(end_date_str)
            
            start_date = validate_start_date(start_dates)
            end_date = validate_end_date(end_dates)

            if start_date > end_date:
                start_date, end_date = end_date, start_date

            weather_lst = []
            s = requests.session()

            for dt in rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date):
                year = dt.year
                month = dt.month

                response = fetch_html(session=s, city=city_code, year=year, month=month)

                if response:
                    weather_data = parse_weather(response)
                    if weather_data:
                        weather_lst += weather_data
                    else:
                        msg = '解析失敗，稍後重試'
                else:
                    msg = '獲取失敗，稍後重試'

            if not msg:
                weather_data = [['日期', '最高溫度', '最低溫度', '天氣', '風向', '風力', 'AQI', 'AQI水平']]
                header_names = ['ymd', 'bWendu', 'yWendu', 'tianqi', 'fengxiang', 'fengli', 'aqi', 'aqiInfo']
                for weather in weather_lst:
                    try:
                        d = datetime.strptime(weather.get(header_names[0], ''), '%Y-%m-%d')
                        if start_date <= d <= end_date:
                            weather_data.append(dict2list(weather, header_names))
                    except:
                        pass
                # print(weather_data)
                filename = quote('{}-{}天氣'.format(start_date_str, end_date_str)) # 不支持中文
                return ExcelResponse(weather_data, output_filename=filename)
        else:
            msg = '信息不全'
        
        context = {
            'message': msg,
        }

        return render(request, 'index.html', context=context)
    else:
        return render(request, 'index.html')

def validate_date(date, min_default=False):
    min_date = datetime(2011, 1, 1)
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

def fetch_html(session, city, year, month):
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Referer': 'http://tianqi.2345.com/wea_history/{}.htm'.format(city),
        'User-Agent': choice(user_agents),
    }

    url = 'http://tianqi.2345.com/t/wea_history/js/{year:04d}{month:02d}/{city}_{year:04d}{month:02d}.js'.format(
        year=year, city=city, month=month
    )

    try:
        r = session.get(url, headers=headers)
        if r.status_code == 200:
            return r.text
        else:
            return ''
    except:
        return ''

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
        # print(weather_lst)
        return weather_lst
    except Exception as e:
        # print(e)
        return []

def dict2list(dict_to_convert, keys, default=''):
    result = []
    for key in keys:
        result.append(dict_to_convert.get(key, default))
    
    return result