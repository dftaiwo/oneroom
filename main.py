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
import re



class Connection(ndb.Model):
	channel_id = ndb.StringProperty(indexed=True)
	site_id = ndb.StringProperty(indexed=True)
	display_name = ndb.StringProperty();
	user_id = ndb.StringProperty(indexed=True);
	user_image= ndb.StringProperty();
	timestamp = ndb.DateTimeProperty(auto_now_add=True)

class Scene(ndb.Model):
	name = ndb.StringProperty()
	next_id = ndb.IntegerProperty(default=0, indexed=False)
	site_id = ndb.StringProperty(indexed=True)
	connections = ndb.StructuredProperty(Connection, repeated=True)
	
class UserMessage(webapp2.RequestHandler):
	def post(self):
		
		channel_id = self.request.get('channel_id');
		siteId  = self.request.get('site_id');
		clientSeq = self.request.get('client_seq');
		currentUser = getUserInfo(clientSeq);
		msgTimeStamp = self.request.get('timestamp');
		msg = self.request.get('msg');
		
		xssCleaner = xss.XssCleaner();#get rid of potentially harmful code
		msg = xssCleaner.strip(msg);
		
			
		#msg="{0} says ".format(currentUser.user_id);
		logging.info('Received MESSAGE [%s %s]' % (channel_id, clientSeq))
		sequence = memcache.incr("sequence", initial_value=0)
		
		if sequence is None:
			sequence = 0
		clientKey = getClientKey(siteId);
		scene_k = ndb.Key('Scene', clientKey);
		scene = scene_k.get()
 		if scene is None:
 			logging.info('MainHandler creating Scene')
 			scene = Scene(name='Scene_{0}'.format(siteId), id=clientKey)

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
					'client_seq' : clientSeq,
					'channel_id' : channel_id,
					'msg' : msg,
					'totalClients':totalClients,
					'server_time' : int(time.time() * 1000),
					'site_id':siteId,
					'sender': currentUser
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
		clientKey = getClientKey(client_id);
		scene_k = ndb.Key('Scene', clientKey);
		pass
		# inform other clients about the new addition
		# inform this client about the other clients
# 		scene = scene_k.get()
# 		send_client_list(scene.connections)

def getClientKey(siteId):
	return "Scene_{0}".format(siteId);

class ChatWidget(webapp2.RequestHandler):#this should generate a js file just for the specified 'site'
	def get(self):
		siteId =  self.request.get('site_id','default');
		channel_id = "";
		token = "";
		clientKey = getClientKey(siteId);
		scene_k = ndb.Key('Scene', clientKey);
		scene = scene_k.get()
		if scene is None:
			logging.info('ChatWidget creating Scene')
			scene = Scene(name='Scene_{0}'.format(siteId), id=clientKey)

		# take this opportunity to cull expired channels
		removed = remove_expired_connections(scene.connections)
		if removed:
			send_client_list(scene.connections)

		channel_id = str(scene.next_id)
		scene.next_id += 1
		scene.connections.append(Connection(channel_id=channel_id,site_id=siteId))
		token = channel.create_channel(channel_id,duration_minutes=30)
		scene.put()
		logging.info('ChatWidget channel_id=%s' % channel_id)
	
		requestUrl = self.request.uri;
		
		chatServerUrlIndex = requestUrl.index('widget');
		
		chatServerUrl = requestUrl[0:chatServerUrlIndex];
		
		template_values = {
								'channelToken' : token,
								'channelId' : channel_id,
								'client_seq':channel_id,
								'totalClients': len(scene.connections),
								'myNickName':"Me",
								'siteId':siteId,
								'chatServerUrl':chatServerUrl,
						}
		
		path = os.path.join(os.path.dirname(__file__), "templates/widget.html")
		self.response.out.write(template.render(path, template_values));

class ChatJs(webapp2.RequestHandler):#this should generate a js file just for the specified 'site'
	def get(self):
		siteId =  self.request.get('site_id','default');
		requestUrl = self.request.uri;
		
		chatServerUrlIndex = requestUrl.index('config');
		chatServerUrl = requestUrl[0:chatServerUrlIndex];
		template_values = {
								'siteId':siteId,
								'chatServerUrl':chatServerUrl,
						}
		path = os.path.join(os.path.dirname(__file__), "templates/config.js")
		self.response.headers['Content-Type'] = 'application/javascript'
		self.response.out.write(template.render(path, template_values));


	


class RefreshToken(webapp2.RequestHandler):#this should generate a js file just for the specified 'site'
	def post(self):
		siteId =  self.request.get('site_id','default');
		#currentUser = requireAuth(self);
		displayName=self.request.get('name','anonymous');
		userId=self.request.get('user_id',0);
		userImage=self.request.get('image','/assets/img/avatar-02.svg');
		
		channel_id = "";
		token = "";
		clientKey = getClientKey(siteId);
		scene_k = ndb.Key('Scene', clientKey);
		scene = scene_k.get()
		if scene is None:
			logging.info('MainHandler creating Scene')
			scene = Scene(name='Scene_{0}'.format(siteId), id=clientKey)

		# take this opportunity to cull expired channels
		removed = remove_expired_connections(scene.connections)
		if removed:
			send_client_list(scene.connections)

		channel_id = str(scene.next_id)
		scene.next_id += 1
		userInfo = {
			'id':userId,
			'name':displayName,
			'image':userImage
		}
		storeUserInfo(userId,userInfo);  
		
		scene.connections.append(Connection(channel_id=channel_id,site_id=siteId,display_name=displayName,user_id=userId,user_image=userImage));
		
		token = channel.create_channel(channel_id,duration_minutes=30)
		scene.put()
		logging.info('MainHandler channel_id=%s' % channel_id)
	
		tokenResponse = {'result':{
								'token' : token,
								'site_id':siteId,
								'channel_id' : channel_id,
								'client_seq':userId, #currentUser.user_id(),
								'totalClients': len(scene.connections),
								}
						}
		
		self.response.headers['Content-Type'] = 'application/javascript'
		self.response.out.write(json.dumps(tokenResponse));	
				
		
class MainHandler(webapp2.RequestHandler):
	def get(self):
		loadHeader(self,'Welcome');
		template_values = {
					
		}
		path = os.path.join(os.path.dirname(__file__), "templates/welcome.html")
		self.response.out.write(template.render(path, template_values));
		loadFooter(self);

class DemoPage(webapp2.RequestHandler):
	def get(self):
		loadHeader(self,'Demo Page');
		path = os.path.join(os.path.dirname(__file__), "templates/demo.html")
		self.response.out.write(template.render(path, {}));
		loadFooter(self);


def loadHeader(self,pageTitle):
	#self.response.out.write(logOutUrl);
	template_values = {
		'page_title' :pageTitle
	}
	
	path = os.path.join(os.path.dirname(__file__), "templates/header.html")
	self.response.out.write(template.render(path, template_values));


def loadFooter(self):
	template_values = {}
	path = os.path.join(os.path.dirname(__file__), "templates/footer.html")
	self.response.out.write(template.render(path, template_values));	


class CreateWidget(webapp2.RequestHandler):
	def get(self):
		template_values = {}
		
		widgetUrl = self.request.get('url',False);
		widgetTitle  = self.request.get('title',False);
		if widgetUrl and widgetTitle:
			urlIsValid = is_valid_url(widgetUrl);
			logging.info('	 urlIsValid [%s]' % (urlIsValid))
			if urlIsValid is True:
				pass
			else:
				template_values['form_error']="'{0}' is not a valid url. Please check and try again.".format(widgetUrl);
		
		loadHeader(self,'Create Widget');
		currentUser = requireAdminAuth(self);
		path = os.path.join(os.path.dirname(__file__), "templates/create_widget.html")
		self.response.out.write(template.render(path,template_values));
		loadFooter(self);
	

def is_valid_url(url):
	#http://stackoverflow.com/questions/827557/how-do-you-validate-a-url-with-a-regular-expression-in-python
	regex = re.compile(
	r'^https?://'  # http:// or https://
	r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
	r'localhost|'  # localhost...
	r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
	r'(?::\d+)?'  # optional port
	r'(?:/?|[/?]\S+)$', re.IGNORECASE)
	return url is not None and regex.search(url)
   	
def storeUserInfo(userId ,userInfo):
	memcache.add(key=userId, value=userInfo, time=21600);
	


def requireAdminAuth(self):
	currentUser = users.get_current_user()
 	if currentUser:
  		return currentUser;
 	else:
 		googleLoginUrl = users.create_login_url(self.request.uri);
 		self.redirect(googleLoginUrl,False,True)
	

def getUserInfo(userId):
	userInfo = memcache.get(userId);
	return userInfo;


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

			
app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/config',ChatJs),
    ('/widget',ChatWidget),
    ('/demo',DemoPage),
    ('/createWidget',CreateWidget),
    ('/refreshToken',RefreshToken),
    ('/message', UserMessage),
    ('/_ah/channel/connected/', UserConnected),
    ('/_ah/channel/disconnected/', UserDisconnected)
    ], debug=True)
