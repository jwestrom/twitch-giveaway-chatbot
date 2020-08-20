import os
import csv
import random
import configparser
import logging
import sys
import asyncio
from typing import Set, Any

from twitchio.ext import commands

logger = logging.getLogger('bot')


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

    def __contains__(self, user: str):
        return user in self._users


class Scoreboard:
    _filename: str

    def __init__(self, filename=None):
        self._filename = filename or 'scoreboard.txt'
        self._scoreboard = {}

    def load(self):
        logger.info('Loading scoreboard...')

        if not os.path.isfile(self._filename):
            return

        scoreboard = {}
        try:
            with open(self._filename, 'r') as _file:
                rows = csv.reader(_file, delimiter=' ', quotechar='"')
                for row in rows:
                    name, temp = row
                    scub = [str(temp)[1:-1][0], str(temp)[1:-1][-1]]
                    if name and scub[0] is not None:
                        scoreboard[name.lower()] = [int(scub[0]), bool(scub[1])]
            self._scoreboard = scoreboard

        except Exception as e:
            logger.warning(f'Fail to load "{self._filename}":', e)

        for name, temp in scoreboard.items():
            score = str(temp)[1:-1][0]
            logger.debug(f'Scoreboard: {name} {score}')

    def save(self):
        logger.info(f'Saving scoreboard to "{self._filename}"')

        with open(self._filename, 'w', newline='') as _file:
            _writer = csv.writer(_file, delimiter=' ', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            _writer.writerows(self._scoreboard.items())

    def get(self, user: str) -> list:
        return self._scoreboard.get(user)

    def reset(self, user: str) -> None:
        self._scoreboard[user] = [0, self._scoreboard.get(user)[1]]

    def add(self, user: str, sub: bool) -> None:
        logger.info(f"Adding user {user}.")
        if user in self._scoreboard:
            self._scoreboard[user] = [self._scoreboard.get(user)[0] + 1, bool(sub)]
        else:
            self._scoreboard[user] = [1, bool(sub)]

    def bump(self, user: str, points: int) -> None:
        logger.debug(f'Bumping score for user {user} with {points}')
        if user in self._scoreboard:
            self._scoreboard[user] = [self._scoreboard.get(user)[0] + points, self._scoreboard.get(user)[1]]
        else:
            self._scoreboard[user] = [points, self._scoreboard.get(user)[1]]


class Giveaway:
    scoreboard: Scoreboard
    ignorelist: IgnoreList
    opened: bool
    participants: Set[str]
    sub_luck: int

    def __init__(self, sub_luck: int):
        self.scoreboard = Scoreboard()
        self.ignorelist = IgnoreList()
        self.ignorelist.load()

        self.opened = False
        self.sub_luck = sub_luck
        self.participants = set()
        self._lock = asyncio.Lock()

    def open(self):
        if not self.opened:
            self.scoreboard.load()
            self.opened = True
            self.participants = set()
            logger.info('Giveaway is opened')

    def reopen(self):
        if not self.opened:
            self.opened = True
            logger.info('Giveaway is re-opened')

    def close(self):
        if self.opened:
            self.scoreboard.save()
            self.opened = False
            logger.info('Giveaway is closed')
            logger.debug(f'Participants: {self.participants}')

    def winner(self):
        if self.opened:
            logger.warning("Can't pick a winner: Close giveaway to pick a winner")
            return

        if not self.participants:
            logger.warning("Can't pick a winner: No participants")
            return

        participants = list(self.participants)
        weights = []
        for name in participants:
            terrance = self.scoreboard.get(name)
            weights.append(terrance[0])
            if terrance[1]:
                weights[-1] = weights[-1] * self.sub_luck
        winner_name, *_ = random.choices(participants, weights)

        self.scoreboard.reset(winner_name)
        self.participants.discard(winner_name)
        self.scoreboard.save()

        return winner_name

    def add(self, name: str, sub: bool) -> None:
        logger.debug(f'Trying to add participant {name}')

        if not self.opened:
            return
        if name in self.participants:
            return
        if name in self.ignorelist:
            logger.debug(f'User {name} in ignorelist')
            return

        self.participants.add(name)
        self.scoreboard.add(name, sub)


class Bot(commands.Bot):
    SUB_LUCK: int
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
        self.SUB_LUCK = config['bot'].getint('SUB_LUCK', fallback=1)

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
        self.giveaway = Giveaway(self.SUB_LUCK)
        logger.info(f'Bot {self.nick} ready')

    async def event_message(self, message):
        await self.handle_commands(message)

    @commands.command(name='open', aliases=['o'])
    async def open_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!open')
                if not self.giveaway.opened:
                    self.giveaway.open()
                    await ctx.send_me(f'== Giveaway is opened == Type !giveaway to participate')

    @commands.command(name='reopen', aliases=['reo'])
    async def reopen_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!reopen')
                if not self.giveaway.opened:
                    self.giveaway.reopen()
                    await ctx.send_me(f'== Giveaway is RE-opened == Harry up! Type !giveaway to participate')

    @commands.command(name='close', aliases=['c'])
    async def close_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!close')
                if self.giveaway.opened:
                    self.giveaway.close()
                    await ctx.send_me(f'== Giveaway is closed == Pick the winner')

    @commands.command(name='winner', aliases=['w'])
    async def winner_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!winner')
                winner = self.giveaway.winner()
                if winner is not None:
                    await ctx.send_me(f'== The winner is @{winner} ==')
                else:
                    await ctx.send_me(f'== No participants ==')

    @commands.command(name='giveaway', aliases=['ga'])
    async def giveaway_command(self, ctx):
        self.giveaway.add(ctx.author.name.lower(), ctx.author.is_subscriber)

    @commands.command(name='scoreboard', aliases=['sb'])
    async def scoreboard_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!scoreboard')
                for name in self.giveaway.participants:
                    logger.info(f'Scoreboard: {name} {self.giveaway.scoreboard.get(name)}')

    @commands.command(name='ignorelist')
    async def ignorelist_command(self, ctx):
        if self.is_admin(ctx.author):
            async with self._lock:
                logger.info('!ignorelist')
                for name in self.giveaway.ignorelist._users:
                    logger.info(f'Ignorelist: {name}')

    @commands.command(name='me')
    async def me_command(self, ctx):
        if ctx.author.is_subscriber:
            await ctx.send_me(f'==> {ctx.author.name} is sub SeemsGood')
        else:
            await ctx.send_me(f'==> {ctx.author.name} is not sub Kappa')

    async def event_command_error(self, ctx, error):
        logger.error(f'Error: {error}', exc_info=True)


if __name__ == "__main__":
    file_handler = logging.FileHandler('bot.log')
    file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)

    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        level=logging.DEBUG,
        handlers=[file_handler, stream_handler],
    )

    bot = Bot()
    bot.run()
