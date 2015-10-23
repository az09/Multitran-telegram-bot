#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
#TODO
#-what if there is no such word. Process "Варианты замены"
#-language choice

import logging
import telegram
from time import time
from os import path, listdir, walk
import socket
import pickle #module for saving dictionaries to file
from bs4 import BeautifulSoup #HTML parser
import re

from webpage_reader import getHTML_specifyEncoding

#if a connection is lost and getUpdates takes too long, an error is raised
socket.setdefaulttimeout(30)

logging.basicConfig(format = u'[%(asctime)s] %(filename)s[LINE:%(lineno)d]# %(levelname)-8s  %(message)s', 
	level = logging.WARNING)


############
##PARAMETERS
############

#A filename of a file containing a token.
TOKEN_FILENAME = 'token'

#A path where subscribers list is saved.
SUBSCRIBERS_BACKUP_FILE = '/tmp/multitran_bot_subscribers_bak'


HELP_MESSAGE = '''
Help message
'''

START_MESSAGE = "Welcome! Type /help to get help."

HELP_BUTTON = "⁉️" + "Help"
PICK_LANGUAGE_BUTTON = "🇬🇧🇫🇷🇮🇹🇩🇪🇳🇱🇪🇸 Pick Language"
BACK_BUTTON = "⬅️ Back"

#Indicies that correspond to various languages on Multitran
LANGUAGE_INDICIES = {
"🇬🇧 English" :1
, "🇩🇪 Deutsch":3
, "🇫🇷 Français":4
, "🇪🇸 Español":5
, "🇮🇹 Italiano":23
, "[] Esperanto":34
, "🇳🇱 Nederlands":24
}

def split_list(alist,max_size=1):
	"""Yield successive n-sized chunks from l."""
	for i in range(0, len(alist), max_size):
		yield alist[i:i+max_size]

MAIN_MENU_KEY_MARKUP = [[PICK_LANGUAGE_BUTTON],[HELP_BUTTON]]
LANGUAGE_PICK_KEY_MARKUP = list(  split_list( list(LANGUAGE_INDICIES.keys()) ,3)  ) + [[BACK_BUTTON]]

################
###GLOBALS######
################

with open(path.join(path.dirname(path.realpath(__file__)), TOKEN_FILENAME),'r') as f:
	BOT_TOKEN = f.read().replace("\n","")

#############
##METHODS###
############


###############
###CLASSES#####
###############

class TelegramBot():
	"""The bot class"""

	LAST_UPDATE_ID = None

	#{chat_id: [LANGUAGE_INDEX], ...}
	subscribers = {}

	def __init__(self, token):
		super(TelegramBot, self).__init__()
		self.bot = telegram.Bot(token)
		#get list of all image files
		self.loadSubscribers()

	def loadSubscribers(self):
		'''
		Loads subscribers from a file
		'''
		try:
			with open(SUBSCRIBERS_BACKUP_FILE,'rb') as f:
				self.subscribers = pickle.load(f)
				print("self.subscribers",self.subscribers)
		except FileNotFoundError:
			logging.warning("Subscribers backup file not found. Starting with empty list!")

	def saveSubscribers(self):
		'''
		Saves a subscribers list to file
		'''
		with open(SUBSCRIBERS_BACKUP_FILE,'wb') as f:
			pickle.dump(self.subscribers, f, pickle.HIGHEST_PROTOCOL)

	def sendMessage(self,chat_id,text,key_markup=MAIN_MENU_KEY_MARKUP):
		logging.warning("Replying to " + str(chat_id) + ": " + text)
		while True:
			try:
				self.bot.sendMessage(chat_id=chat_id,
					text=text,
					parse_mode='Markdown',
					reply_markup=telegram.ReplyKeyboardMarkup(key_markup)
					)
			except Exception as e:
				if "Message is too long" in str(e):
					self.sendMessage(chat_id=chat_id
						,text="Error: Message is too long!"
						)
					break
				else:
					logging.error("Could not send message. Retrying! Error: " + str(e))
					continue
			break

	def sendPic(self,chat_id,pic):
		while True:
			try:
				logging.debug("Picture: " + str(pic))
				#set file read cursor to the beginning. This ensures that if a file needs to be re-read (may happen due to exception), it is read from the beginning.
				pic.seek(0)
				self.bot.sendPhoto(chat_id=chat_id,photo=pic)
			except Exception as e:
				logging.error("Could not send picture. Retrying! Error: " + str(e))
				continue
			break

	def getUpdates(self):
		'''
		Gets updates. Retries if it fails.
		'''
		#if getting updates fails - retry
		while True:
			try:
				updates = self.bot.getUpdates(offset=self.LAST_UPDATE_ID, timeout=3)
			except Exception as e:
				logging.error("Could not read updates. Retrying! Error: " + str(e))
				continue
			break
		return updates


	def echo(self):
		bot = self.bot

		updates = self.getUpdates()

		for update in updates:
			chat_id = update.message.chat_id
			Message = update.message
			from_user = Message.from_user
			message = Message.text
			logging.warning("Received message: " + str(chat_id) + " " + from_user.username + " " + message)

			#register the user if not present in the subscribers list
			try:
				self.subscribers[chat_id]
			except KeyError:
				self.subscribers[chat_id] = 1

			if message == "/start":
				self.sendMessage(chat_id=chat_id
					,text=START_MESSAGE
					)
			elif message == "/help" or message == HELP_BUTTON:
				self.sendMessage(chat_id=chat_id
					,text=HELP_MESSAGE
					)
			elif message == PICK_LANGUAGE_BUTTON:
				self.sendMessage(chat_id=chat_id
					,text="Select language"
					,key_markup=LANGUAGE_PICK_KEY_MARKUP
					)
			elif message == BACK_BUTTON:
				self.sendMessage(chat_id=chat_id
					,text="Back to Main Menu"
					)
			elif message in list(LANGUAGE_INDICIES.keys()):
				#message is a language pick
				pass
				self.subscribers[chat_id] = LANGUAGE_INDICIES[message]
				self.sendMessage(chat_id=chat_id
					,text="Language is set to " + message
					)
			else:
				if message[0] == "/":
					message = message[1:]

				page = getHTML_specifyEncoding('http://www.multitran.ru/c/m.exe?l1='+str(self.subscribers[chat_id]) +'&s=' + message, encoding='cp1251',method='replace')
				soup = BeautifulSoup(page)

				temp1 = [i for i in soup.find_all('table') if not i.has_attr('class') and not i.has_attr('id') and not i.has_attr('width') and i.has_attr('cellpadding') and i.has_attr('cellspacing') and i.has_attr('border') 
				and not len(i.find_all('table'))
				]
				print("temp1 ", temp1)
				print("len(temp1) ", len(temp1))

				def process_result(temp1):
					result = ""
					for tr in temp1.find_all('tr'):
						tds = tr.find_all('td')
						def translations_row():
							result = "_" + tr.find_all('a')[0].text + "_" + " "*5
							for a in tr.find_all('a')[1:]:
								if not 'i' in [i.name for i in a.children]:
									result +=  a.text + "; "
							return result

						if tds[0].has_attr('bgcolor'):
							if tds[0]['bgcolor'] == "#DBDBDB":
								result += "\n" + "*" + tr.text.split("|")[0].replace(tr.find_all('em')[0].text if tr.find_all('em') else "","").replace("в начало","") + "*" + ( ( " "*5 + "_" + tr.find_all('em')[0].text  + "_") if tr.find_all('em') else "" )
							else:
								result += translations_row()
						else:
							result += translations_row()
						result += "\n"
					return result



				result=""
				#maybe the request is in Russian?
				if not len(temp1):
					page = getHTML_specifyEncoding('http://www.multitran.ru/c/m.exe?l1=2&l2='+ str(self.subscribers[chat_id]) + '&s=' + message, encoding='cp1251',method='replace')
					soup = BeautifulSoup(page)

					temp1 = [i for i in soup.find_all('table') if not i.has_attr('class') and not i.has_attr('id') and not i.has_attr('width') and i.has_attr('cellpadding') and i.has_attr('cellspacing') and i.has_attr('border') and not len(i.find_all('table'))]

					# Maybe there is no such word?
					if not len(temp1):
						result="*Word not found!*"
						varia = soup.find_all('td',string=re.compile("Варианты"))
						print("varia",varia)
						if varia:
							logging.warning("Есть варианты замены!")
							# print(varia[0].find_next_sibling("td").find_all('a'))
							# quit()
							result += "\n" + "*Possible replacements: *" + varia[0].find_next_sibling("td").text

					else:
						#request is in Russian
						temp1= temp1[0]
						result = process_result(temp1)

				else:
					#request is in foreign language
					temp1= temp1[0]
					result = process_result(temp1)

				result += "\nCurrent language is " + list(LANGUAGE_INDICIES.keys())[list(LANGUAGE_INDICIES.values()).index(self.subscribers[chat_id]) ]

				try:
					self.sendMessage(chat_id=chat_id
						,text=str(result)
						)
				except Exception as e:
					logging.error("Could not process message. Error: " + str(e))

			# Updates global offset to get the new updates
			self.LAST_UPDATE_ID = update.update_id + 1


def main():
	bot = TelegramBot(BOT_TOKEN)

	#main loop
	while True:
		bot.echo()

if __name__ == '__main__':
	main()