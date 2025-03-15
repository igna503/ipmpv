import os
import json
from flask import request, make_response

class Localization:
	"""Handles localization for IPMPV"""

	def __init__(self, default_language='en'):
		"""Initialize the localization system"""
		self.default_language = default_language
		self.translations = {}
		self.available_languages = []
		self.cookie_name = 'ipmpv_language'
		self.cookie_max_age = 31536000  # 1 year in seconds
		self._load_translations()

	def _load_translations(self):
		"""Load all translation files from the locales directory"""
		locales_dir = os.path.join(os.path.dirname(__file__), 'locales')

		# Create locales directory if it doesn't exist
		if not os.path.exists(locales_dir):
			os.makedirs(locales_dir)

		# Load each translation file
		for filename in os.listdir(locales_dir):
			if filename.endswith('.json'):
				language_code = filename.split('.')[0]
				self.available_languages.append(language_code)

				with open(os.path.join(locales_dir, filename), 'r', encoding='utf-8') as f:
					self.translations[language_code] = json.load(f)

		# If no translations are available, create an empty one for the default language
		if not self.translations:
			self.available_languages.append(self.default_language)
			self.translations[self.default_language] = {}

	def get_language(self):
		"""Get the current language based on cookies or browser settings"""
		# Check cookie first
		lang_cookie = request.cookies.get(self.cookie_name)
		if lang_cookie and lang_cookie in self.available_languages:
			return lang_cookie

		# Check browser Accept-Language header
		if request.accept_languages:
			for lang in request.accept_languages.values():
				if lang[:2] in self.available_languages:
					return lang[:2]

		# Fallback to default language
		return self.default_language

	def set_language(self, language_code, response=None):
		"""
		Set the current language in a cookie

		Args:
			language_code (str): The language code to set
			response (flask.Response, optional): A Flask response object to add the cookie to

		Returns:
			bool: Whether the language was set successfully
		"""
		if language_code in self.available_languages:
			# If a response was provided, add the cookie to it
			if response:
				response.set_cookie(
					self.cookie_name,
					language_code,
					max_age=self.cookie_max_age,
					path='/',
					httponly=True,
					samesite='Strict'
				)
			return True
		return False

	def translate(self, key, language=None):
		"""Translate a key to the specified or current language"""
		if language is None:
			language = self.get_language()

		# If the language doesn't exist, use default
		if language not in self.translations:
			language = self.default_language

		# If the key exists in the language, return the translation
		if key in self.translations[language]:
			return self.translations[language][key]

		# If not found in the current language, try the default language
		if language != self.default_language and key in self.translations[self.default_language]:
			return self.translations[self.default_language][key]

		# If still not found, return the key itself
		return key

# Create a global localization instance
localization = Localization()

# Helper function to use in templates
def _(key):
	"""Shorthand for translating a key"""
	return localization.translate(key)
