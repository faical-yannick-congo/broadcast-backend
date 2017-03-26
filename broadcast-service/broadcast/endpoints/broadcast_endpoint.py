import simplejson as json

from flask.ext.api import status
import flask as fk

from broadcastdb.common import crossdomain
from broadcast import app, SERVICE_URL, service_response, fetch_city, get_user_city, get_country, get_one_number, get_cities, menu
from broadcastdb.common.models import Broadcast
from time import gmtime, strftime

import mimetypes
import traceback
import datetime
import random
import string
from io import StringIO
import hashlib
import phonenumbers
from phonenumbers.phonenumberutil import region_code_for_country_code
from phonenumbers.phonenumberutil import region_code_for_number
import pycountry

from geopy import geocoders
from tzwhere import tzwhere
from pytz import timezone
import pytemperature
from translate import Translator

@app.route(SERVICE_URL + '/menu', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def service_menu():
    if fk.request.method == 'GET':
        return service_response(200, 'Service Menu', menu())
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/history/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def broadcast_by_city(country, city):
    if fk.request.method == 'GET':
        if city == 'all':
            if country == 'all':
                broadcasts = [b.info() for b in Broadcast.objects()]
            else:
                broadcasts = [b.info() for b in Broadcast.objects(country=country)]
        else:
            broadcasts = [b.info() for c in Broadcast.objects(city=city.lower(), country=country)]
        return service_response(200, 'City: {0} of Country: {1} broadcast history'.format(city.lower(), country), {'size':len(broadcasts), 'history':broadcasts})
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/today/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def broadcast_today_city(country, city):
    if fk.request.method == 'GET':
        _country = get_country(country)
        if _country is None:
            return service_response(204, 'Unknown country', 'We could not find this country.')
        else:
            lat = _country["lat"]
            lng = _country["lng"]
            if lat == "":
                lat = 0.00
                lng = 0.00
            tz = tzwhere.tzwhere()
            timeZoneStr = tz.tzNameAt(lat, lng)
            timeZoneObj = timezone(timeZoneStr)
            now_time = datetime.datetime.now(timeZoneObj)
            day = str(now_time).split(" ")[0]
            if city == 'all':
                if country == 'all':
                    broadcasts = [c.info() for c in Broadcast.objects(day=day)]
                else:
                    broadcasts = [c.info() for c in Broadcast.objects(day=day, country=country)]
            else:
                broadcasts = [c.info() for c in Broadcast.objects(day=day, city=city.lower(), country=country)]
            return service_response(200, 'City: {0} of Country: {1} broadcast today: {2}'.format(city.lower(), country, day), {'size':len(broadcasts), 'today':broadcasts})
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/message/delete/<broadcast_id>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def delete_broadcast(broadcast_id):
    if fk.request.method == 'GET':
        _broadcast = Broadcast.objects.with_id(broadcast_id)
        if _broadcast:
            _broadcast.delete()
            return service_response(200, 'Deletion succeeded', 'Broadcast {0} deleted.'.format(broadcast_id))
        else:
            return service_response(204, 'Unknown broadcast', 'No corresponding broadcast found.')
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/message/send', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def message_send():
    if fk.request.method == 'POST':
        if fk.request.data:
            print(fk.request.data)
            data = json.loads(fk.request.data)
            sender = data.get('sender', None)
            content = data.get('content', None)
            recipient = data.get('recipient', 'all')
            country = data.get('country', None)
            city = data.get('city', None)

            if sender is None and content is None:
                return service_response(405, 'Message send denied', 'A message has to contain a sender number and a content.')
            else:
                _country = get_country(country)
                if _country is None:
                    return service_response(204, 'Unknown country', 'We could not find this country.')
                else:
                    lat = _country["lat"]
                    lng = _country["lng"]
                    if lat == "":
                        lat = 0.00
                        lng = 0.00
                    tz = tzwhere.tzwhere()
                    timeZoneStr = tz.tzNameAt(lat, lng)
                    timeZoneObj = timezone(timeZoneStr)
                    now_time = datetime.datetime.now(timeZoneObj)
                    day = str(now_time).split(" ")[0]
                    date = datetime.datetime.strptime(day, "%Y-%m-%d")
                    ignore, language = get_cities(country)
                    translator = Translator(to_lang=language)
                    if city:
                        city = fetch_city(city, _country["name"].split(":")[0])
                    else:
                        city = "all"
                    if city is None:
                        return service_response(405, translator.translate('Message send denied'), translator.translate('You must register first to our servcies. Send us your city to +12408052607'))

                    broadcast = Broadcast(created_at=str(datetime.datetime.utcnow()), sender=sender, recipient=recipient, city=city.lower(), country=country, day=day)
                    broadcast.message = content
                    broadcast.save()
                    return service_response(200, translator.translate('Your message was received'), translator.translate('It will be broadcasted soon.'))
        else:
            return service_response(204, 'Message send failed', 'No data submitted.')
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a POST method.')

@app.route(SERVICE_URL + '/message/pushing/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def broadcast_pushing_country(country, city):
    if fk.request.method == 'GET':
        _country = get_country(country)
        if _country is None:
            return service_response(204, 'Unknown country', 'We could not find this country.')
        else:
            lat = _country["lat"]
            lng = _country["lng"]
            if lat == "":
                lat = 0.00
                lng = 0.00
            tz = tzwhere.tzwhere()
            timeZoneStr = tz.tzNameAt(lat, lng)
            timeZoneObj = timezone(timeZoneStr)
            now_time = datetime.datetime.now(timeZoneObj)
            day = str(now_time).split(" ")[0]
            date = datetime.datetime.strptime(day, "%Y-%m-%d")

            if city == "all":
                broadcast_pulled = Broadcast.objects(country=country, status='pulled', day=day).first()
            else:
                broadcast_pulled = Broadcast.objects(city=city.lower(), country=country, status='pulled', day=day).first()

            if broadcast_pulled:
                broadcast_pulled.status = 'pushing'
                broadcast_pulled.save()
                ignore, language = get_cities(country)
                broadcast_pushing =broadcast_pulled.info()
                translator = Translator(to_lang=language)
                broadcast_pushing["message"] = translator.translate(broadcast_pushing["message"])
                return service_response(200, translator.translate('Broadcast in () today {0}:'.format(day)), broadcast_pushing)
            else:
                return service_response(204, 'No broadcast to send', "no broadcast at this point.")
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/message/pushed/<broadcast_id>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def pushed_broadcast(broadcast_id):
    if fk.request.method == 'GET':
        _broadcast = Broadcast.objects.with_id(broadcast_id)
        if _broadcast:
            _broadcast.status = 'pushed'
            _broadcast.save()
            return service_response(200, 'Broadcast pushed', 'Broadcast {0} was confimed pushed.'.format(broadcast_id))
        else:
            return service_response(204, 'Unknown broadcast', 'No corresponding broadcast found.')
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')
