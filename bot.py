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
    users: Set[str]
    FILENAME: str

    def __init__(self, filename: str = None):
        self.FILENAME = filename or 'ignorelist.txt'
        self.users = set()

    # Loads the ignorelist from file
    def load(self) -> None:
        logger.info('Loading ignorelist...')

        if not os.path.isfile(self.FILENAME):
            logger.info('Ignorelist not found')
            logger.info('Create empty ignorelist...')
            with open(self.FILENAME, 'a') as _file:
                pass

        try:
            with open(self.FILENAME, 'r') as _file:
                self.users = set[line.strip() for line in open(self.FILENAME)]
        except Exception as e:
            print('Fail to load "{self.filename}":', e)

        logger.info(f'{len(self.users)} users ignored')
        logger.debug(f'Ignored users: {self.users}')

    # Saves the ignorelist to file
    def save(self) -> None:
        logger.info('Saving ignorelist...')
        with open(self.FILENAME, 'w') as _file:
            for name in self.users:
                _file.write(f'{name}\n')

    # Adds a username to the ignorelist
    def add(self, name) -> None:
        if name not in self.users:
            logger.info(f'Adding {name} to ignorelist.')
            self.users.add(name)
            self.save()

    # Removes a username from the ignorelist
    def remove(self, name) -> None:
        if name in self.users:
            logger.info(f'Removing {name} from ignorelist.')
            self.users.remove(name)
            self.save()

    # Checks if a username is in the ignorelist
    def __contains__(self, name: str) -> bool:
        return name.lower in self.users


# Class for users in the giveaways. Keeps track of name, subscriber tier, current luck,
# lifetime giveaway entries, giveaway entries since last win and the userid.
class User:
    name: str
    luck: int
    tier: int
    lifetime: int
    since_last_win: int
    id: str

    def __init__(self, name: str, luck: int, tier: int, lifetime: int, since_last_win: int, userid: str = ''):
        self.name = name
        self.tier = tier
        self.luck = luck
        self.lifetime = lifetime
        self.since_last_win = since_last_win
        self.id = f'{userid}'


# Scoreboard that keeps track of all users who have ever participated.
# Is loaded from a file when the program starts.
class Scoreboard:
    FILENAME: str
    scoreboard: Dict[str, User]
    API: APIHandler
    LUCK_BUMP: int
    TIER1_LUCK: int
    TIER2_LUCK: int
    TIER3_LUCK: int
    SKIP_PUNISHMENT: int

    def __init__(self, bump: int, tier1: int, tier2: int, tier3: int, skip_punishment, api: APIHandler, filename=None):
        self.FILENAME = filename or 'scoreboard.txt'
        self.LUCK_BUMP = bump
        self.TIER1_LUCK = tier1
        self.TIER2_LUCK = tier2
        self.TIER3_LUCK = tier3
        self.SKIP_PUNISHMENT = skip_punishment
        self.API = api
        self.scoreboard = {}

    # Load the scoreboard from a file.
    def load(self):
        logger.info('Loading scoreboard...')

        if not os.path.isfile(self.FILENAME):
            logger.warning('Could not find file!')
            logger.info('Creating new scoreboard.')
            return

        scoreboard = {}
        try:
            with open(self.FILENAME, 'r') as _file:
                rows = csv.reader(_file, delimiter=' ', quotechar='"')
                next(rows)
                for row in rows:
                    name, luck, tier, lifetime, since_last_win, userID = row
                    if name is not None:
                        scoreboard[name.lower()] = User(name=name, luck=int(luck),
                                                        tier=int(tier), lifetime=int(lifetime),
                                                        since_last_win=int(since_last_win), userid=userID)
            self.scoreboard = scoreboard

        except Exception as e:
            logger.warning(f'Fail to load "{self.FILENAME}":', e)

        logger.debug("Scoreboard - Name : Luck")
        for user in scoreboard.values():
            logger.debug(f'{user.name} : {user.luck}')

    # Save the scoreboard to a file.
    def save(self):
        logger.info(f'Saving scoreboard to "{self.FILENAME}"')

        with open(self.FILENAME, 'w', newline='') as _file:
            _writer = csv.writer(_file, delimiter=' ', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            _writer.writerow((["Username", "Luck", "Tier", "Lifetime", "Since last win", "ID"]))
            for user in self.scoreboard.values():
                _writer.writerow([user.name, user.luck, user.tier, user.lifetime, user.since_last_win, user.id])

    # Gets a user from the scoreboard.
    def get(self, name: str) -> User:
        return self.scoreboard.get(name)

    # Reset the luck of a user to 0
    def reset(self, name: str) -> None:
        logger.info(f'Reseting {name} to 0 luck and 0 giveaways since last win.')
        self.scoreboard[name].luck = 0
        self.scoreboard[name].since_last_win = 0

    # Punishes a user for participating in a giveaway without being able to claim the price.
    # Used to combat luck farming
    def punish(self, name: str) -> None:
        logger.info(f'Punishing {name} for not claiming giveaway prize. '
                    f'Decreasing current luck by {self.SKIP_PUNISHMENT}%.')
        logger.debug(f'{name} had {self.scoreboard[name].luck}.')
        self.scoreboard[name].luck = int(self.scoreboard[name].luck * ((100 - self.SKIP_PUNISHMENT) / 100))
        logger.debug(f'{name} now has {self.scoreboard[name].luck}.')

    # Adds a user to the scoreboard. This is only called when a user is added to a giveaway.
    # If the user has participated before we increase luck and lifetime by 1
    # If the user is new we set luck and lifetime to 1
    # We also make sure that the user has a twitchID and gets their current subscription status
    def add(self, name: str) -> None:
        logger.info(f"Adding user {name}.")
        if name in self.scoreboard:
            user = self.scoreboard.get(name)
            user.luck += self.LUCK_BUMP
            user.lifetime += 1
            user.since_last_win += 1
            if not user.id:
                user.id = self.API.getuserid(name)
            user.tier = self.getUserTier(user.id)
            self.scoreboard[name] = user
        else:
            user = User(name, luck=self.LUCK_BUMP, tier=0, lifetime=1, since_last_win=1, userid="")
            user.id = self.API.getuserid(name)
            user.tier = self.getUserTier(user.id)
            self.scoreboard[name] = user

    # Gets subscription tier from a user id.
    # Returns an int with that tiers luck
    def getUserTier(self, id: str) -> int:
        tier = self.API.getsubscriptiontier(id)
        if tier == '1000':
            return self.TIER1_LUCK
        elif tier == '2000':
            return self.TIER2_LUCK
        elif tier == '3000':
            return self.TIER3_LUCK
        else:
            return 0

    # Increases the luck of one player by n times the luck_bump
    def bump(self, name: str, points: int) -> None:
        if name in self.scoreboard:
            logger.info(f'Bumping score for user {name} with {points}')
            self.scoreboard[name].luck += (points * self.LUCK_BUMP)
        else:
            logger.warning(f'{name} is not in the scoreboard. Ignoring bump.')

    # Returns a users stats: current luck, sub tier, lifetime participations and amount of giveaways since last win.
    def user_stats(self, name: str) -> [int, int, int]:
        user = self.scoreboard.get(name)
        return [int(user.luck / self.LUCK_BUMP), int(user.tier / 10), user.lifetime, user.since_last_win]

# Class for running the giveaways. Contains logic and draw randomization
class Giveaway:
    scoreboard: Scoreboard
    IGNORE_LIST: IgnoreList
    LUCK_BUMP: int
    opened: bool
    winner: str
    winner_roll: int
    winner_giveaways: int
    participants: Dict[str, User]

    def __init__(self, scoreboard: Scoreboard, luck_bump: int) -> None:
        self.scoreboard = scoreboard
        self.IGNORE_LIST = IgnoreList()
        self.IGNORE_LIST.load()

        self.LUCK_BUMP = luck_bump
        self.opened = False
        self.winner = ""
        self.winner_roll = 0
        self.winner_giveaways = 0
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
            self.winner_roll = 0
            self.winner_giveaways = 0
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

        # If draw() is called and there is already a winner the last winner gets punished for not claiming their prize.
        if self.winner:
            self.scoreboard.punish(self.winner)

        results: Dict[str, int] = {}

        for name, user in self.participants.items():
            results[name] = random.randint(1, 1000) + user.luck + user.tier

        self.winner = max(results, key=results.get)
        self.winner_roll = results[self.winner]
        self.winner_giveaways = int(self.scoreboard.get(self.winner).since_last_win)

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
        if name in self.IGNORE_LIST:
            logger.info(f'{name} is in ignorelist.')
            return

        logger.debug(f"Adding {name} to giveaway.")

        self.scoreboard.add(name)
        self.participants[name] = self.scoreboard.get(name)
        logger.debug(f'{name} added to giveaway.')

    # Returns if the user is in the current giveaway or not.
    def is_participating(self, name) -> bool:
        return name in self.participants


class Bot(commands.Bot):
    TMI_TOKEN: str
    ACCESS_TOKEN: str
    CLIENT_ID: str
    BROADCAST_ID: str
    BOT_NICK: str
    CHANNEL: str
    BOT_PREFIX: str
    ADMINS: [str]
    CASE_SENSITIVE: bool
    REMINDER_ENABLED: bool
    REMINDER_TIME: int

    scoreboard: Scoreboard
    reminder_task: Any
    giveaway_word: str

    # Init for the bot. Reads the config file and sets all values
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('settings.ini')

        self.TMI_TOKEN = config['bot']['TMI_TOKEN']
        self.ACCESS_TOKEN = config['bot']['ACCESS_TOKEN']
        self.CLIENT_ID = config['bot']['CLIENT_ID']
        self.BROADCAST_ID = config['bot']['BROADCAST_ID']
        self.BOT_NICK = config['bot']['BOT_NICK']
        self.CHANNEL = config['bot']['CHANNEL']
        self.BOT_PREFIX = config['bot'].get('BOT_PREFIX', '!')
        self.ADMINS = config['bot']['ADMINS'].split(',')

        # Automatically gets the client/broadcast id of the user if it is missing
        if (not self.BROADCAST_ID) or (self.BROADCAST_ID == 'your_user_accounts_id'):
            self.BROADCAST_ID = str(apihandler.APIHandler.getuseridstatic(accessToken=self.ACCESS_TOKEN,
                                                                          clientid=self.CLIENT_ID,
                                                                          name=self.CHANNEL))
            config['bot']['BROADCAST_ID'] = self.BROADCAST_ID

        self.scoreboard = Scoreboard(bump=config['giveaway'].getint('LUCK_BUMP', fallback=10),
                                     tier1=config['giveaway'].getint('TIER1_LUCK', fallback=300),
                                     tier2=config['giveaway'].getint('TIER2_LUCK', fallback=350),
                                     tier3=config['giveaway'].getint('TIER3_LUCK', fallback=400),
                                     skip_punishment=config['giveaway'].getint('SKIP_PUNISHMENT', fallback=50),
                                     api=apihandler.APIHandler(clientID=self.CLIENT_ID,
                                                               accessToken=self.ACCESS_TOKEN,
                                                               broadcasterID=self.BROADCAST_ID))

        self.CASE_SENSITIVE = config['giveaway'].getboolean('CASE_SENSITIVE', fallback=True)
        self.REMINDER_ENABLED = config['giveaway'].getboolean('REMINDER_ENABLED', fallback=False)
        self.REMINDER_TIME = config['giveaway'].getint('REMINDER_DELAY', fallback=300)
        self.giveaway_word = ''
        self.giveaway = None
        self.blacklist = None

        self._lock = asyncio.Lock()

        super().__init__(
            irc_token=self.TMI_TOKEN,
            nick=self.BOT_NICK,
            prefix=self.BOT_PREFIX,
            initial_channels=[self.CHANNEL],
        )

    # Sends a reminder message every REMINDER_TIME seconds when a giveaway is opened.
    async def giveaway_reminder(self):
        channel = bot.get_channel(self.CHANNEL)
        loop = asyncio.get_event_loop()
        while True:
            logger.info("Sending reminder to the chat.")
            if self.giveaway_word:
                loop.create_task(channel.send_me(f'Giveaway is still open! Make sure to join with: {self.giveaway_word}'))
            else:
                loop.create_task(channel.send_me('Giveaway is still open! Make sure to join with: !giveaway'))
            await asyncio.sleep(self.REMINDER_TIME)


    async def event_pubsub(self, data):
        pass

    # Checks if the user is in the admin list
    def is_admin(self, user) -> bool:
        return user.name.lower() in (name.lower() for name in self.ADMINS)

    # Triggers when the bot is ready
    async def event_ready(self) -> None:
        self.giveaway = Giveaway(scoreboard=self.scoreboard, luck_bump=self.scoreboard.LUCK_BUMP)
        self.scoreboard.load()
        logger.info(f'Bot {self.nick} ready')

    # Reads every message sent in chat. Looks for the giveaway keyword and enters users if a giveaway is open.
    async def event_message(self, ctx) -> None:
        if ctx.author.name.lower() == self.BOT_NICK.lower():
            return
        if self.CASE_SENSITIVE:
            if ctx.content == self.giveaway_word:
                if self.giveaway.opened:
                    logger.debug(f'Adding {ctx.author.name.lower()} to giveaway!')
                    self.giveaway.add(ctx.author.name.lower())
        else:
            if ctx.content.lower() == self.giveaway_word:
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
                logger.info('!open-ing giveaway')
                if not self.giveaway.opened:
                    if self.REMINDER_ENABLED:
                        try:
                            logger.debug("Creating reminder task.")
                            self.reminder_task = asyncio.ensure_future(self.giveaway_reminder())
                        except asyncio.CancelledError:
                            pass

                    self.giveaway.open()
                    word = ctx.content.split(' ')[-1]
                    if word != "!open":
                        if self.CASE_SENSITIVE:
                            self.giveaway_word = word
                        else:
                            self.giveaway_word = word.lower()
                        await ctx.send_me(f'== Giveaway is opened! == '
                                          f'Type {self.giveaway_word} to participate! ==')
                    else:
                        self.giveaway_word = ""
                        await ctx.send_me('== Giveaway is opened! == '
                                          'Type !giveaway to participate! ==')

    # Re-opens a closed giveaway.
    # Admin only
    @commands.command(name='reopen', aliases=['reo'])
    async def reopen_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!reopen-ing giveaway')
                if not self.giveaway.opened:
                    self.giveaway.reopen()
                    if self.giveaway_word:
                        await ctx.send_me(f'== Giveaway is RE-opened == Hurry up! Type {self.giveaway_word} to participate ==')
                    else:
                        await ctx.send_me(f'== Giveaway is RE-opened == Hurry up! Type !giveaway to participate ==')

    # Closes the current giveaway
    # Admin only
    @commands.command(name='close', aliases=['c'])
    async def close_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!close-ing giveaway')
                if self.giveaway.opened:
                    if self.REMINDER_ENABLED: # Only try to cancel the reminder task if reminders are enabled
                        logger.debug("Cancelling reminder task.")
                        self.reminder_task.cancel()
                    self.giveaway.close()
                    await ctx.send_me(f'== Giveaway is closed == Pick the winner')

    # If the giveaway is closed, draw a winner and present them.
    # Admin only
    @commands.command(name='winner', aliases=['w'])
    async def winner_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                self.giveaway_word = '' # Clears the giveaway word to avoid weird effects
                logger.info('!winner')
                self.giveaway.draw()
                winner_name = self.giveaway.winner
                if winner_name:
                    await ctx.send_me(f'== The winner is @{winner_name} == '
                                      f'Winning roll: {self.giveaway.winner_roll} == '
                                      f'It took {self.scoreboard.get(self.giveaway.winner).since_last_win} giveaways '
                                      f'to win ==')
                else:
                    await ctx.send_me(f'== No participants ==')

    # Confirms the winner of the last giveaway.
    # Admin only
    @commands.command(name='confirm', aliases=['cf'])
    async def confirm_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                if self.giveaway.winner:
                    logger.info('!confirm-ing winner.')
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
                for name in self.giveaway.IGNORE_LIST.users:
                    logger.info(f'Ignorelist: {name}')

    # Adds a username to the ignorelist
    @commands.command(name='ignore')
    async def ignore_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                _, user, *_ = ctx.content.split(' ')
                if user:
                    if '@' in user:
                        user = user[1:].lower()
                        logger.info(f'!ignore-ing {user}')
                        self.giveaway.IGNORE_LIST.add(user)
                    else:
                        logger.info(f'!ignore-ing {user.lower()}')
                        self.giveaway.IGNORE_LIST.add(user.lower())

    # Removes a username from the ignorelist
    @commands.command(name='clear')
    async def clear_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            async with self._lock:
                _, user, *_ = ctx.content.split(' ')
                if user:
                    if '@' in user:
                        user = user[1:].lower()
                        logger.info(f'!clear-ing {user}')
                        self.giveaway.IGNORE_LIST.remove(user)
                    else:
                        logger.info(f'!clear-ing {user.lower()}')
                        self.giveaway.IGNORE_LIST.remove(user.lower())

    # Checks if a user is in the current giveaway and presents it in chat
    @commands.command(name='me')
    async def me_command(self, ctx) -> None:
        if self.giveaway.is_participating(ctx.author.name.lower()):
            await ctx.send_me(f'==> {ctx.author.name} is in this Giveaway Pog')
        else:
            await ctx.send_me(f'==> {ctx.author.name} is NOT in this Giveaway KEKW')

    # Gets the stats for a user and presents them in chat
    @commands.command(name='stats', aliases=['lucky', 'howlucky'])
    async def luck_command(self, ctx) -> None:
        user_stats = self.scoreboard.user_stats(ctx.author.name.lower())
        await ctx.send_me(f'{ctx.author.name} has a current luck of {user_stats[0]}% '
                          f'with a subscription bonus of {user_stats[1]}% '
                          f'for a total of {user_stats[0] + user_stats[1]}%. '
                          f'{ctx.author.name} has participated in {user_stats[2]} total giveaways'
                          f' and {user_stats[3]} since their last win!')

    # Increases a users luck by a number
    @commands.command(name='bump', aliases=['giveluck'])
    async def bump_command(self, ctx) -> None:
        if self.is_admin(ctx.author):
            _, user, luck, *_ = ctx.content.split(' ')
            if user and luck:
                logger.info(f'Trying to bump{user[1:].lower()} by {luck}')
                self.scoreboard.bump(user[1:].lower(), int(luck))

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
