'''
Created on Jul 2, 2014

@author: dftaiwo
'''
from google.appengine.ext import db

class ChatUser(db.Model):
    nickname = db.StringProperty(multiline=True)
    user_id = db.StringProperty()
    joined = db.IntegerProperty()
    status = db.IntegerProperty()
