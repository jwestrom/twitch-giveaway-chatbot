import os
import csv
import random
import configparser
import logging
import sys
import asyncio
from typing import Set, Dict, Any
from datetime import date
from twitchio.ext import commands

import apihandler
from apihandler import APIHandler

logger = logging.getLogger(__name__)


# Ignorelist of users that are not allowed to participate in giveaways.
class IgnoreList:
    _users: Set[str]
    _filename: str

    def __init__(self, filename: str = None):
        self._filename = filename or 'ignorelist.txt'
        self._users = set()

    # Loads the ignorelist from file
    def load(self) -> None:
        logger.info('Loading ignorelist...')

        if not os.path.isfile(self._filename):
            logger.info('Ignorelist not found')
            logger.info('Create empty ignorelist...')
            with open(self._filename, 'a') as _file:
                pass

        try:
            with open(self._filename, 'r') as _file:
                rows = csv.reader(_file, delimiter=' ', quotechar='"')
                for user, *_ in rows:
                    if user:
                        self._users.add(user.lower())
        except Exception as e:
            print('Fail to load "{self.filename}":', e)

        logger.info(f'{len(self._users)} users ignored')
        logger.debug(f'Ignored users: {self._users}')

    # Saves the ignorelist to file
    # Not implemented
    def save(self) -> None:
        logger.info('Saving ignorelist...')
        with open(self._filename, 'w') as _file:
            _writer = csv.writer(_file, delimiter=' ', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            _writer.writerows(self._users)

    # Adds a username to the ignorelist
    # Not implemented
    def add(self, name) -> None:
        if name not in self._users:
            self._users.add(name.lower())

    # Checks if a username is in the ignorelist
    def __contains__(self, name: str) -> bool:
        return name.lower in self._users


# Class for users in the giveaways. Keeps track of name, subscriber tier, current luck and lifetime giveaway entries.
class User:
    name: str
    luck: int
    tier: int
    lifetime: int
    id: str

    def __init__(self, name: str, luck: int, tier: int, lifetime: int, userid: str = ''):
        self.name = name
        self.tier = tier
        self.luck = luck
        self.lifetime = lifetime
        self.id = f'{userid}'


# Scoreboard that keeps track of all users who have ever participated.
# Is loaded from a file when the program starts.
class Scoreboard:
    filename: str
    scoreboard: Dict[str, User]
    api: APIHandler
    luck_bump: int
    tier1_luck: int
    tier2_luck: int
    tier3_luck: int

    def __init__(self, bump: int, tier1: int, tier2: int, tier3: int, api: APIHandler, filename=None):
        self.filename = filename or 'scoreboard.txt'
        self.luck_bump = bump
        self.tier1_luck = tier1
        self.tier2_luck = tier2
        self.tier3_luck = tier3
        self.api = api
        self.scoreboard = {}

    # Load the scoreboard from a file.
    def load(self):
        logger.info('Loading scoreboard...')

        if not os.path.isfile(self.filename):
            logger.error("Could not find file!")
            return

        scoreboard = {}
        try:
            with open(self.filename, 'r') as _file:
                rows = csv.reader(_file, delimiter=' ', quotechar='"')
                next(rows)
                for row in rows:
                    name, tier, luck, lifetime, userID = row
                    if name is not None:
                        scoreboard[name.lower()] = User(name, int(luck), int(tier), int(lifetime), userID)
            self.scoreboard = scoreboard

        except Exception as e:
            logger.warning(f'Fail to load "{self.filename}":', e)

        logger.debug("Scoreboard - Name : Luck")
        for user in scoreboard.values():
            logger.debug(f'{user.name} : {user.luck}')

    # Save the scoreboard to a file.
    def save(self):
        logger.info(f'Saving scoreboard to "{self.filename}"')

        with open(self.filename, 'w', newline='') as _file:
            _writer = csv.writer(_file, delimiter=' ', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            _writer.writerow((["Username", "Luck", "Tier", "Lifetime", "ID"]))
            for user in self.scoreboard.values():
                _writer.writerow([user.name, user.luck, user.tier, user.lifetime, user.id])

    # Gets a user from the scoreboard.
    def get(self, name: str) -> User:
        return self.scoreboard.get(name)

    # Reset the luck of a user to 0
    def reset(self, name: str) -> None:
        self.scoreboard[name].luck = 0

    # Adds a user to the scoreboard. This is only called when a user is added to a giveaway.
    # If the user has participated before we increase luck and lifetime by 1
    # If the user is new we set luck and lifetime to 1
    # We also make sure that the user has a twitchID and gets their current subscription status
    def add(self, name: str) -> None:
        logger.info(f"Adding user {name}.")
        if name in self.scoreboard:
            user = self.scoreboard.get(name)
            user.luck += self.luck_bump
            user.lifetime += 1
            if not user.id:
                user.id = self.api.getuserid(name)
            tier = self.api.getsubscriptiontier(user.id)
            if tier == '1000':
                user.tier = self.tier1_luck
            elif tier == '2000':
                user.tier = self.tier2_luck
            elif tier == '3000':
                user.tier = self.tier3_luck
            else:
                user.tier = 0
            self.scoreboard[name] = user
        else:
            self.scoreboard[name] = User(name, luck=self.luck_bump, tier=0, lifetime=1)

    # Increases the luck of one player by points
    def bump(self, name: str, points: int) -> None:
        logger.debug(f'Bumping score for user {name} with {points}')
        if name in self.scoreboard:
            self.scoreboard[name].luck = self.scoreboard[name].luck + points
        else:
            logger.warning(f'{name} is not in the scoreboard. Ignoring bump.')

# Class for running the giveaways. Contains logic and draw randomization
class Giveaway:
    scoreboard: Scoreboard
    ignorelist: IgnoreList
    opened: bool
    winner: str
    winner_roll: int
    participants: Dict[str, User]

    def __init__(self, scoreboard: Scoreboard) -> None:
        self.scoreboard = scoreboard
        self.ignorelist = IgnoreList()
        self.ignorelist.load()

        self.opened = False
        self.winner = ""
        self.winner_roll = 0
        self.participants = {}
        self._lock = asyncio.Lock()

    # Opens the giveaway. Loads the scoreboard from file and clears values from last giveaway.
    def open(self) -> None:
        if not self.opened:
            if self.winner:
                self.confirm_winner()
                logger.debug(f'Winner was not manually confirmed in last giveaway.'
                             f' Last winner automatically confirmed.')
            self.scoreboard.load()
            self.opened = True
            self.winner = ""
            self.participants = {}
            logger.info('Giveaway is opened')

    # Re-opens the giveaway without drawing a winner
    def reopen(self) -> None:
        if not self.opened:
            self.opened = True
            logger.info('Giveaway is re-opened')

    # Closes the giveaway and prepares for draw.
    def close(self) -> None:
        if self.opened:
            self.scoreboard.save()
            self.opened = False
            logger.info('Giveaway is closed')
            logger.debug(f'Participants: {self.participants}')

    # Performs the draw and selects a winner.
    def draw(self) -> None:
        if self.opened:
            logger.warning("Can't pick a winner: Close giveaway to pick a winner")
            return

        if not self.participants:
            logger.warning("Can't pick a winner: No participants")
            return

        results: Dict[str, int] = {}

        for name, user in self.participants.items():
            results[name] = random.randint(1, 1000) + user.luck + user.tier

        self.winner = max(results, key=results.get)
        self.winner_roll = results[self.winner]
        logger.debug(f"Drawing winner... Winner is {self.winner} that won with a value of: {self.winner_roll}")

        self.participants.pop(self.winner)

    # Confirms the winner of the last giveaway. Resets the luck of the winner and saves the scoreboard.
    def confirm_winner(self) -> None:
        self.scoreboard.reset(self.winner)
        self.scoreboard.save()

    # Adds a user to the giveaway and to the scoreboard.
    # Checks if a giveaway is opened, if the user is already in the giveaway and if the name is on the ignorelist
    def add(self, name: str) -> None:
        logger.debug(f'Trying to add participant {name}')

        if not self.opened:
            logger.warning(f'Giveaway is not opened!')
            return
        if name in self.participants:
            logger.info(f'{name} is already in giveaway.')
            return
        if name in self.ignorelist:
            logger.info(f'{name} is in ignorelist.')
            return

        logger.debug(f"Adding {name} to giveaway.")

        self.scoreboard.add(name)
        self.participants[name] = self.scoreboard.get(name)
        logger.debug(f'{name} added to giveaway.')

    # Returns if the user is in the current giveaway or not.
    def is_participating(self, name) -> bool:
        return name in self.participants

    # Returns a users stats: current luck, sub tier and lifetime participations.
    def user_stats(self, name) -> [int, int, int]:
        user = self.scoreboard.get(name)
        return [user.luck, user.tier, user.lifetime]


class Bot(commands.Bot):
    ADMINS: [str]
    BOT_PREFIX: str
    CHANNEL: str
    BOT_NICK: str
    TMI_TOKEN: str
    ACCESS_TOKEN: str
    CLIENT_ID: str
    _scoreboard: Scoreboard
    _giveaway_word: str
    _remindertime: int
    _remindertask: Any

    # Init for the bot. Reads the config file and sets all values
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('settings.ini')

        self.TMI_TOKEN = config['bot']['TMI_TOKEN']
        self.ACCESS_TOKEN = config['bot']['ACCESS_TOKEN']
        self.CLIENT_ID = config['bot']['CLIENT_ID']
        self.BOT_NICK = config['bot']['BOT_NICK']
        self.CHANNEL = config['bot']['CHANNEL']
        self.BOT_PREFIX = config['bot'].get('BOT_PREFIX', '!')
        self.ADMINS = config['bot']['ADMINS'].split(',')
        self._scoreboard = Scoreboard(config['bot'].getint('LUCK_BUMP', fallback=10),
                                      config['bot'].getint('TIER1_LUCK', fallback=300),
                                      config['bot'].getint('TIER2_LUCK', fallback=350),
                                      config['bot'].getint('TIER3_LUCK', fallback=400),
                                      apihandler.APIHandler(config['bot']['CLIENT_ID'],
                                                            config['bot']['ACCESS_TOKEN'],
                                                            config['bot']['BROADCAST_ID']))
        self._remindertime = config['bot'].getint('REMINDER_DELAY', fallback=300)
        self._giveaway_word = ''
        self.giveaway = None
        self.blacklist = None

        self._lock = asyncio.Lock()

        super().__init__(
            irc_token=self.TMI_TOKEN,
            nick=self.BOT_NICK,
            prefix=self.BOT_PREFIX,
            initial_channels=[self.CHANNEL],
        )

    async def giveaway_reminder(self):
        while await asyncio.sleep(self._remindertime, result=True):
            channel = bot.get_channel(self.CHANNEL)
            loop = asyncio.get_event_loop()

            if self._giveaway_word:
                loop.create_task(channel.send_me(f'Giveaway is still open! Make sure to join with: {self._giveaway_word}'))
            else:
                loop.create_task(channel.send_me('Giveaway is still open! Make sure to join with: !giveaway'))


    async def event_pubsub(self, data):
        pass

    # Checks if the user is in the admin list
    def is_admin(self, user) -> bool:
        return user.name.lower() in (name.lower() for name in self.ADMINS)

    # Triggers when the bot is ready
    async def event_ready(self) -> None:
        self.giveaway = Giveaway(scoreboard=self._scoreboard)
        self._scoreboard.load()
        logger.info(f'Bot {self.nick} ready')

    # Reads every message sent in chat. Looks for the giveaway keyword and enters users if a giveaway is open.
    async def event_message(self, ctx) -> None:
        if ctx.author.name.lower() == self.BOT_NICK.lower():
            return
        if ctx.content == self._giveaway_word:
            if self.giveaway.opened:
                logger.debug(f'Adding {ctx.author.name.lower()} to giveaway!')
                self.giveaway.add(ctx.author.name.lower())
        await self.handle_commands(ctx)

    # Opens a new giveaway
    # Admin only
    @commands.command(name='open', aliases=['o'])
    async def open_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!open')
                if not self.giveaway.opened:
                    try:
                        self._remindertask = asyncio.get_event_loop().call_later(5)
                    except asyncio.CancelledError:
                        pass

                    self.giveaway.open()
                    word = ctx.content.split(' ')[-1]
                    if word != "!open":
                        self._giveaway_word = word
                        await ctx.send_me(f'== Giveaway is opened! == '
                                          f'Giveaway word is: {self._giveaway_word} ==')
                    else:
                        await ctx.send_me('== Giveaway is opened! == '
                                          'Type !giveaway to participate ==')

    # Re-opens a closed giveaway.
    # Admin only
    @commands.command(name='reopen', aliases=['reo'])
    async def reopen_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!reopen')
                if not self.giveaway.opened:
                    self.giveaway.reopen()
                    await ctx.send_me(f'== Giveaway is RE-opened == Harry up! Type !giveaway to participate')

    # Closes the current giveaway
    # Admin only
    @commands.command(name='close', aliases=['c'])
    async def close_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!close')
                if self.giveaway.opened:
                    self._remindertask.cancel()
                    self.giveaway.close()
                    await ctx.send_me(f'== Giveaway is closed == Pick the winner')

    # If the giveaway is closed, draw a winner and present them.
    # Admin only
    @commands.command(name='winner', aliases=['w'])
    async def winner_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                self._giveaway_word = '' # Clears the giveaway word to avoid weird effects
                logger.info('!winner')
                self.giveaway.draw()
                winner = self.giveaway.winner
                if winner:
                    await ctx.send_me(f'== The winner is @{winner} == '
                                      f'Winning roll: {self.giveaway.winner_roll}==')
                else:
                    await ctx.send_me(f'== No participants ==')

    # Confirms the winner of the last giveaway.
    # Admin only
    @commands.command(name='confirm', aliases=['cf'])
    async def confirm_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                if self.giveaway.winner:
                    logger.info('Winner has been !confirm ed')
                    self.giveaway.confirm_winner()
                    await ctx.send_me(f'{self.giveaway.winner} has been confirmed as winner!')
                else:
                    logger.warning('No winner has been selected yet. Please draw a winner first.')

    # Enters the user into the current giveaway.
    @commands.command(name='giveaway', aliases=['ga'])
    async def giveaway_command(self, ctx) -> None:
        if self.giveaway.opened:
            logger.debug(f'Adding {ctx.author.name.lower()} to giveaway!')
            self.giveaway.add(ctx.author.name.lower())
        else:
            await ctx.send_me(f'There is currently no giveaway open.')

    # Prints, in the bot console, all users in the current giveaway, their luck stat and their tier stat
    @commands.command(name='scoreboard', aliases=['sb'])
    async def scoreboard_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!scoreboard')
                logger.info('Scoreboard:')
                logger.info('Name Luck Tier')
                for name, user in self.giveaway.participants.items():
                    logger.info(f'Name: {name} Luck: {user.luck} Tier: {user.tier}')

    # Prints the ignorelist in the bot console
    @commands.command(name='ignorelist')
    async def ignorelist_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!ignorelist')
                for name in self.giveaway.ignorelist._users:
                    logger.info(f'Ignorelist: {name}')

    # Dummy command for later implementation of !ignore command
    @commands.command(name='ignore')
    async def ignore_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!ignore')
                logger.info('Command currently not implemented')

    # Checks if a user is in the current giveaway and presents it in chat
    @commands.command(name='me')
    async def me_command(self, ctx) -> None:
        if self.giveaway.is_participating(ctx.author.name):
            await ctx.send_me(f'==> {ctx.author.name} is in this Giveaway chevel3Gasm')
        else:
            await ctx.send_me(f'==> {ctx.author.name} is NOT in this Giveaway KEKW')

    # Gets the stats for a user and presents them in chat
    @commands.command(name='stats', aliases=['lucky', 'howlucky'])
    async def luck_command(self, ctx) -> None:
        user_stats = self.giveaway.user_stats(ctx.author.name)
        user_stats[0] = user_stats[0] / 10
        if user_stats[1] != 0:
            user_stats[1] = user_stats[1]/10

        await ctx.send_me(f'{ctx.author.name} has a current luck of {user_stats[0]}% '
                          f'with a subscription bonus of {user_stats[1]}% '
                          f'for a total of {user_stats[0] + user_stats[1]}%. '
                          f'{ctx.author.name} has participated in {user_stats[2]} giveaways!')

    # Increases a users luck by a number
    @commands.command(name='bump', aliases=['giveluck'])
    async def bump_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            _, user, luck, *_ = ctx.content.split(' ')
            if user and luck:
                self._scoreboard.bump(user[1:], int(luck))

    async def event_command_error(self, ctx, error) -> None:
        logger.error(f'Error: {error}', exc_info=True)


if __name__ == "__main__":
    file_handler = logging.FileHandler(f'{date.today().strftime("%Y-%m-%d")}-bot.log')
    file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)

    logging.basicConfig(format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                        level=logging.DEBUG, handlers=[file_handler, stream_handler])

    bot = Bot()
    bot.run()
