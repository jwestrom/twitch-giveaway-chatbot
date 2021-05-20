import os
import csv
import random
import configparser
import logging
import sys
import asyncio
import json
from typing import Set, Any, Dict

from twitchio.ext import commands

logger = logging.getLogger('bot')

# Ignorelist of users that are not allowed to participate in giveaways.
class IgnoreList:
    _users: Set[str]
    _filename: str

    def __init__(self, filename: str = None):
        self._filename = filename or 'ignorelist.txt'
        self._users = set()

    def load(self):
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

    def __contains__(self, name: str):
        return name in self._users

# Class for users in the giveaways. Keeps track of name, subscriber tier, current luck and lifetime giveaway entries.
class User:
    name: str
    luck: int
    subscriber_tier: int
    lifetime: int

    def __init__(self, name: str, luck: int, tier: int, lifetime: int):
        self.name = name
        self.tier = tier
        self.luck = luck
        self.lifetime = lifetime

    def toCsv(self):
        return f'{self.name} {self.tier} {self.luck} {self.lifetime}'

# Scoreboard that keeps track of all users who have ever participated.
# Is loaded from a file when the program starts.
class Scoreboard:
    _filename: str

    def __init__(self, filename=None):
        self._filename = filename or 'scoreboard.txt'
        self._scoreboard = {}

    # Load the scoreboard from a file.
    def load(self):
        logger.info('Loading scoreboard...')

        if not os.path.isfile(self._filename):
            logger.error("Could not find file!")
            return

        scoreboard = {}
        try:
            with open(self._filename, 'r') as _file:
                rows = csv.reader(_file, delimiter=' ', quotechar='"')
                for row in rows:
                    name, tier, luck, lifetime = row
                    if name is not None:
                        scoreboard[name.lower()] = User(name, luck, tier, lifetime)
            self._scoreboard = scoreboard

        except Exception as e:
            logger.warning(f'Fail to load "{self._filename}":', e)

        for user in scoreboard.items():
            logger.debug(f'Scoreboard: {user.name} {user.luck}')

    # Save the scoreboard to a file.
    def save(self):
        logger.info(f'Saving scoreboard to "{self._filename}"')

        with open(self._filename, 'w', newline='') as _file:
            _writer = csv.writer(_file, delimiter=' ', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for u in Scoreboard:
                _writer.writerow(u.toCsv)

    # Gets a user from the scoreboard.
    def get(self, name: str) -> User:
        return self._scoreboard.get(name)

    # Reset the luck of a user to 0
    def reset(self, name: str) -> None:
        self._scoreboard[name].luck = 0

    # Adds a user to the scoreboard. This is only called when a user is added to a giveaway.
    # If the user has participated before we increase luck and lifetime by 1
    # If the user is new we set luck and lifetime to 1
    def add(self, name: str, tier: int) -> None:
        logger.info(f"Adding user {name}.")
        if name in self._scoreboard:
            user = self._scoreboard.get(name)
            user.luck = user.luck + 1
            user.tier = tier
            user.lifetime = user.lifetime + 1
            self._scoreboard[name] = user
        else:
            self._scoreboard[name] = User(name, luck=1, tier=tier, lifetime=1)

    def bump(self, name: str, points: int) -> None:
        logger.debug(f'Bumping score for user {name} with {points}')
        if name in self._scoreboard:
            self._scoreboard[name].luck = self._scoreboard[name].luck + points
        else:
            logger.warning(f'{name} is not in the scoreboard. Ignoring bump.')



class Giveaway:
    scoreboard: Scoreboard
    ignorelist: IgnoreList
    opened: bool
    winner: str
    winner_roll: int
    participants: Dict[str, User]

    def __init__(self) -> None:
        self.scoreboard = Scoreboard()
        self.ignorelist = IgnoreList()
        self.ignorelist.load()

        self.opened = False
        self.winner = ""
        self.participants = {}
        self._lock = asyncio.Lock()

    # Opens the giveaway. Loads the scoreboard from file and clears values from last giveaway.
    def open(self) -> None:
        if not self.opened:
            if self.winner:
                self.confirm_winner()
                logger.debug(f'Winner was not manually confirmed in last giveaway. Last winner automatically confirmed.')
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

        results: dict[str, int]

        for name, user in self.participants.items():
            results[name] = random.randint(1, 100) + user.luck + user.tier

        self.winner = max(results, key=results.get)
        self.winner_roll = results[self.winner]
        logger.debug(f"Drawing winner... Winner is {self.winner} that won with a value of: {self.winner_roll}")

        self.participants.discard(self.winner)

    # Confirms the winner of the last giveaway. Resets the luck of the winner and saves the scoreboard.
    def confirm_winner(self) -> None:
        self.scoreboard.reset(self.winner)
        self.scoreboard.save()

    # Adds a user to the giveaway and to the scoreboard.
    def add(self, name: str, tier: int) -> None:
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

        self.scoreboard.add(name, tier)
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
    TIER1_LUCK: int
    TIER2_LUCK: int
    TIER3_LUCK: int
    ADMIN: str
    BOT_PREFIX: str
    CHANNEL: str
    BOT_NICK: str
    TMI_TOKEN: str

    def __init__(self):
        config = configparser.ConfigParser()
        config.read('settings.ini')

        self.TMI_TOKEN = config['bot']['TMI_TOKEN']
        self.BOT_NICK = config['bot']['BOT_NICK']
        self.CHANNEL = config['bot']['CHANNEL']
        self.BOT_PREFIX = config['bot'].get('BOT_PREFIX', '!')
        self.ADMIN = config['bot']['ADMIN']
        self.TIER1_LUCK = config['bot'].getint('TIER1_LUCK', fallback=30)
        self.TIER2_LUCK = config['bot'].getint('TIER2_LUCK', fallback=35)
        self.TIER3_LUCK = config['bot'].getint('TIER3_LUCK', fallback=40)


        self.giveaway = None
        self.blacklist = None

        self._lock = asyncio.Lock()

        super().__init__(
            irc_token=self.TMI_TOKEN,
            nick=self.BOT_NICK,
            prefix=self.BOT_PREFIX,
            initial_channels=[self.CHANNEL],
        )

    async def event_pubsub(self, data):
        pass

    def is_admin(self, user):
        return user.name.lower() == self.ADMIN.lower()

    async def event_ready(self):
        self.giveaway = Giveaway()
        logger.info(f'Bot {self.nick} ready')

    async def event_message(self, message):
        await self.handle_commands(message)

    # Opens a new giveaway
    # Admin only
    @commands.command(name='open', aliases=['o'])
    async def open_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!open')
                if not self.giveaway.opened:
                    self.giveaway.open()
                    await ctx.send_me(f'== Giveaway is opened == Type !giveaway to participate')

    # Re-opens a closed giveaway.
    # Admin only
    @commands.command(name='reopen', aliases=['reo'])
    async def reopen_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!reopen')
                if not self.giveaway.opened:
                    self.giveaway.reopen()
                    await ctx.send_me(f'== Giveaway is RE-opened == Harry up! Type !giveaway to participate')

    # Closes the current giveaway
    # Admin only
    @commands.command(name='close', aliases=['c'])
    async def close_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!close')
                if self.giveaway.opened:
                    self.giveaway.close()
                    await ctx.send_me(f'== Giveaway is closed == Pick the winner')

    # If the giveaway is closed, draw a winner and present them.
    # Admin only
    @commands.command(name='winner', aliases=['w'])
    async def winner_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!winner')
                self.giveaway.draw()
                winner = self.giveaway.winner
                if winner is not None:
                    await ctx.send_me(f'== The winner is @{winner} =='
                                      f'== Winning roll: {self.giveaway.winner_roll}==')
                else:
                    await ctx.send_me(f'== No participants ==')

    # Confirms the winner of the last giveaway.
    # Admin only
    @commands.command(name='confirm', aliases=['cf'])
    async def confirm_command(self, ctx):
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
    async def giveaway_command(self, ctx):
        if self.giveaway.opened:
            self.giveaway.add(ctx.author.name.lower(), ctx.author.is_subscriber)
        else:
            await ctx.send_me(f'There is currently no giveaway open.')

    # Prints, in the bot console, all users in the current giveaway, their luck stat and their tier stat
    @commands.command(name='scoreboard', aliases=['sb'])
    async def scoreboard_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!scoreboard')
                for name, user in self.giveaway.participants.items():
                    logger.info(f'Scoreboard: {name} Luck: {user.luck} Tier: {user.tier}')

    @commands.command(name='ignorelist')
    async def ignorelist_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!ignorelist')
                for name in self.giveaway.ignorelist._users:
                    logger.info(f'Ignorelist: {name}')

    @commands.command(name='me')
    async def me_command(self, ctx):
        if self.giveaway.is_participating(ctx.author.name):
            await ctx.send_me(f'==> {ctx.author.name} is in this Giveaway chevel3Gasm')
        else:
            await ctx.send_me(f'==> {ctx.author.name} is NOT in this Giveaway KEKW')

    @commands.command(name='stats')
    async def luck_command(self, ctx):
        user_stats = self.giveaway.user_stats(ctx.author.name)
        await ctx.send_me(f'{ctx.author.name} has a current luck of {user_stats[0]} and has participated in {user_stats[1]} giveaways!'
                          f'')

    async def event_command_error(self, ctx, error):
        logger.error(f'Error: {error}', exc_info=True)


if __name__ == "__main__":
    file_handler = logging.FileHandler('bot.log')
    file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)

    logging.basicConfig(format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s', level=logging.DEBUG, handlers=[file_handler, stream_handler])

    bot = Bot()
    bot.run()
