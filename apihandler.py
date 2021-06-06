import logging
import sys

import requests
from typing import List, Dict
from datetime import date

logger = logging.getLogger(__name__)

# Handles API requests to the twitch API
class APIHandler:
    clientID: str
    accessToken: str
    broadcasterID: str

    # Init for the class. Calls for logging init and checks the access token.
    def __init__(self, clientID: str, accessToken: str, broadcasterID: str):
        self.clientID = clientID
        self.accessToken = accessToken
        self.broadcasterID = broadcasterID
        self.__init_logging__()
        self.checkaccesstoken()

    # Init for the logger
    def __init_logging__(self):
        file_handler = logging.FileHandler(f'{date.today().strftime("%Y-%m-%d")}-bot.log')
        file_handler.setLevel(logging.DEBUG)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.ERROR)
        logging.basicConfig(filename=f'{date.today().strftime("%Y-%m-%d")}-api.log',
                            filemode='a',
                            format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                            level=logging.DEBUG)

    # Checks if our access token is still valid. Will prompt the user to create a new one if needed.
    def checkaccesstoken(self):
        headers = {'Authorization': f'OAuth {self.accessToken}'}
        url = ' https://id.twitch.tv/oauth2/validate'
        logger.info('Checking if our access token is valid.')
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logger.info('Got 200 response. Token is still valid.')
        else:
            logger.critical(
                'Access token has expired! Follow instructions in settings.ini to create a new one!')
            raise RuntimeError('Access token is not valid. Trying to exit...')

    # Gets the userID for a users name
    def getuserid(self, name: str) -> int:
        headers = {'Authorization': f'Bearer {self.accessToken}', 'Client-Id': self.clientID}
        url = 'https://api.twitch.tv/helix/users'
        payload = {'login': name}
        logger.info(f'Sending request for userid of user: {name}')
        response = requests.get(url, headers=headers, params=payload)
        logger.info('Got response from API! Parsing and returning.')
        return response.json()['data'][0]['id'] # Returns the id value of the first entry in data

    #Static method to get the clientID/broadcasterID when it is missing
    @staticmethod
    def getuserid(clientid: str, accessToken: str, name: str) -> int:
        headers = {'Authorization': f'Bearer {accessToken}', 'Client-Id': clientid}
        url = 'https://api.twitch.tv/helix/users'
        payload = {'login': name}
        response = requests.get(url, headers=headers, params=payload)
        return response.json()['data'][0]['id'] # Returns the id value of the first entry in data

    # Gets the subscription tiers for a list of users
    def getsubscriptiontiers(self, userids: List[str]) -> Dict[str, int]:
        headers = {'Authorization': f'Bearer {self.accessToken}', 'Client-Id': self.clientID}
        url = 'https://api.twitch.tv/helix/subscriptions?'
        payload = {'broadcaster_id': self.broadcasterID,'user_id': userids}
        logger.info(f'Sending request for subscription tiers of {userids}')
        response = requests.get(url, headers=headers, params=payload)
        logger.info('Got response from API! Parsing and returning.')
        data = response.json()['data']
        idwithtier = {}

        for user in data:
            idwithtier[user['user_id']] = user['tier']

        for id in userids:
            if f'{id}' in idwithtier:
                pass
            else:
                idwithtier[f'{id}'] = 0

        return idwithtier

    # Gets the subscription tier of a single user
    def getsubscriptiontier(self, userid: str) -> int:
        headers = {'Authorization': f'Bearer {self.accessToken}', 'Client-Id': self.clientID}
        url = 'https://api.twitch.tv/helix/subscriptions?'
        payload = {'broadcaster_id': self.broadcasterID, 'user_id': userid}
        logger.info(f'Sending request for subscription tiers of {userid}')
        response = requests.get(url, headers=headers, params=payload)
        logger.info('Got response from API! Parsing and returning.')
        data = response.json()['data']
        if data:
            return data[0]
        return 0


