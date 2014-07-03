#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
from google.appengine.api import channel
from google.appengine.api import memcache
from google.appengine.api.channel.channel import InvalidMessageError, \
	MAXIMUM_MESSAGE_LENGTH
from google.appengine.ext import db
from google.appengine.ext import ndb
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import login_required
from google.appengine.api import users

from datetime import datetime
from datetime import timedelta

import json
import logging
import os
import random
import string
import time
from libs import xss

from oauth2client import client
from apiclient import sample_tools
				
def send_client_list(connections):
	clients = []
	for c in connections:
		clients.append(c.channel_id)
	message = json.dumps({
		'type' : 'clientsList',
		'clients' : clients,
		'totalClients': len(clients),
	})
	for c in connections:
		channel.send_message(c.channel_id, message)
		logging.info('	 sending client_list to [%s]' % (c.channel_id))



def remove_expired_connections(connections):
	removed = False
	for c in connections:
		time_diff = datetime.now() - c.timestamp
		max_time = timedelta(hours=2)
		if time_diff >= max_time:
			logging.info('Removing expired connection [%s] timedelta=%s' % (c.channel_id, str(c.timestamp)))
			connections.remove(c)
			removed = True
	return removed
					
def id_generator(size=6, chars=string.ascii_letters + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))   


class Connection(ndb.Model):
	channel_id = ndb.StringProperty()
	timestamp = ndb.DateTimeProperty(auto_now_add=True)

class Scene(ndb.Model):
	name = ndb.StringProperty()
	next_id = ndb.IntegerProperty(default=0, indexed=False)
	connections = ndb.StructuredProperty(Connection, repeated=True)
	
class UserMessage(webapp2.RequestHandler):
	def post(self):
		currentUser = requireAuth(self);
		channel_id = self.request.get('channel_id');
		clientSeq = self.request.get('client_seq');
		msgTimeStamp = self.request.get('timestamp');
		msg = self.request.get('msg');
		
		xssCleaner = xss.XssCleaner();#get rid of potentially harmful code
		msg = xssCleaner.strip(msg);
		
		logging.info('Received MESSAGE [%s %s]' % (channel_id, clientSeq))
		sequence = memcache.incr("sequence", initial_value=0)
		
		if sequence is None:
			sequence = 0
		scene_k = ndb.Key('Scene', 'scene1')
		scene = scene_k.get()
		totalClients = len(scene.connections)
		self.response.out.write(json.dumps(
						{
						'posted':True,
						'totalClients':totalClients,
						'msgTimeStamp':msgTimeStamp
						}
				));
		
		
		
		# echo message back to all users
		message = json.dumps({
					'type' : 'newMessage',
					'sequence' : sequence,
					'timestamp' : msgTimeStamp,
					'clientSeq' : clientSeq,
					'channel_id' : channel_id,
					'msg' : msg,
					'totalClients':totalClients,
					'server_time' : int(time.time() * 1000),
					'senderName':currentUser.nickname()
				});
		tStart = datetime.now()
		channel.send_message(channel_id, message)
		tTotal = datetime.now() - tStart
		logging.info('   responded to sender [%s] (%dms)' % (channel_id, tTotal.microseconds / 1000))

		if len(scene.connections) > 1:
			logging.info('   broadcasting to %i clients' % (len(scene.connections) - 1))
			for c in scene.connections:
				if c.channel_id != channel_id:
					tStart = datetime.now()
					channel.send_message(c.channel_id, message)
					tTotal = datetime.now() - tStart
					logging.info('	 broadcast to [%s] (%dms)' % (c.channel_id, tTotal.microseconds / 1000))



class UserDisconnected(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('from')
		logging.info('Received DISCONNECT from %s' % client_id)
		scene_k = ndb.Key('Scene', 'scene1')
		scene = scene_k.get()
		if scene is not None:
			for c in scene.connections:
				if c.channel_id == client_id:
					logging.info('   removing client %s' % client_id)
					scene.connections.remove(c)
					scene.put()
					# inform other clients
					send_client_list(scene.connections)
					return


class UserConnected(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('from')
		logging.info('Received CONNECT from %s' % client_id)
		# inform other clients about the new addition
		# inform this client about the other clients
		scene_k = ndb.Key('Scene', 'scene1')
		scene = scene_k.get()
		send_client_list(scene.connections)

def requireAuth(self):
# 	argv=["main.py"]
# 	service, flags = sample_tools.init(
# 	argv, 'plus', 'v1', __doc__, __file__,
# 	scope='https://www.googleapis.com/auth/plus.me')
# 	people_resource = service.people()
# 	people_document = people_resource.get(userId='me').execute()
# 	self.response.out.write("Hello");
 	currentUser = users.get_current_user()
 	if currentUser:
  		userId = currentUser.user_id();
  		memcache.add(key=userId, value=currentUser.nickname(), time=21600);
 		return currentUser;
 	else:
 		self.redirect('/login',False,True)

class LoginHandler(webapp2.RequestHandler):
	def get(self):
		
		googleLoginUrl = users.create_login_url('/');
		
		template_values = {
					'googleLoginUrl' : googleLoginUrl,
							
			}
		path = os.path.join(os.path.dirname(__file__), "templates/login.html")
		self.response.out.write(template.render(path, template_values));
		
		
class MainHandler(webapp2.RequestHandler):
	
	def get(self):
		currentUser = requireAuth(self);
		channel_id = "";
		token = "";
		scene_k = ndb.Key('Scene', 'scene1')
		scene = scene_k.get()
		if scene is None:
			logging.info('MainHandler creating Scene')
			scene = Scene(name='Scene 1', id='scene1')

		# take this opportunity to cull expired channels
		removed = remove_expired_connections(scene.connections)
		if removed:
			send_client_list(scene.connections)

		channel_id = str(scene.next_id)
		scene.next_id += 1
		scene.connections.append(Connection(channel_id=channel_id))
		token = channel.create_channel(channel_id,duration_minutes=300)
		scene.put()
		logging.info('MainHandler channel_id=%s' % channel_id)
	
		logOutUrl = users.create_logout_url('/');
		
		
		template_values = {
								'token' : token,
								'channel_id' : channel_id,
								'clientSeq':currentUser.user_id(),
								'totalClients': len(scene.connections),
								'nickName':currentUser.nickname(),
								'logoutUrl':logOutUrl
						}
		path = os.path.join(os.path.dirname(__file__), "templates/chatroom.html")
		self.response.out.write(template.render(path, template_values));
		
	

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/login',LoginHandler),
    ('/message', UserMessage),
    ('/_ah/channel/connected/', UserConnected),
    ('/_ah/channel/disconnected/', UserDisconnected)
    ], debug=True)
