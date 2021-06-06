import logging
import requests
from typing import List, Dict
from datetime import date


# Handles API requests to the twitch API
class APIHandler:
    clientID: str
    accessToken: str
    broadcasterID: str
    logger = logging.getLogger(__name__)

    def __init__(self, clientID: str, accessToken: str, broadcasterID: str):
        self.clientID = clientID
        self.accessToken = accessToken
        self.broadcasterID = broadcasterID
        logging.basicConfig(filename=f'{date.today().strftime("%Y-%m-%d")}-api.log',
                            filemode='a',
                            format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                            level=logging.DEBUG)

    # Gets the userID for a users name
    def getuserid(self, name: str) -> int:
        headers = {'Authorization': f'Bearer {self.accessToken}', 'Client-Id': self.clientID}
        url = 'https://api.twitch.tv/helix/users'
        payload = {'login': name}
        self.logger.info(f'Sending request for userid of user: {name}')
        response = requests.get(url, headers=headers, params=payload)
        self.logger.info('Got response from API! Parsing and returning.')
        return response.json()['data'][0]['id'] # Returns the id value of the first entry in data

    # Gets the subscription tiers for a list of users
    def getsubscriptiontiers(self, userids: List[str]) -> Dict[str, int]:
        headers = {'Authorization': f'Bearer {self.accessToken}', 'Client-Id': self.clientID}
        url = 'https://api.twitch.tv/helix/subscriptions?'
        payload = {'broadcaster_id': self.broadcasterID,'user_id': userids}
        self.logger.info(f'Sending request for subscription tiers of {userids}')
        response = requests.get(url, headers=headers, params=payload)
        self.logger.info('Got response from API! Parsing and returning.')
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
        self.logger.info(f'Sending request for subscription tiers of {userid}')
        response = requests.get(url, headers=headers, params=payload)
        self.logger.info('Got response from API! Parsing and returning.')
        data = response.json()['data']
        if data:
            return data[0]
        return 0
