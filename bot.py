import csv
import random
import configparser
from twitchio.ext import commands


class Giveaway:
    def __init__(self, filename=None):
        self.filename = filename or 'scoreboard.txt'
        self.scoreboard = {}
        self.opened = False
        self.participants = set()

    def read_scoreboard(self):
        print('Reading scoreboard...')
        self.scoreboard = {}
        try:
            with open(self.filename, 'r') as _file:
                rows = csv.reader(_file, delimiter=' ', quotechar='"')
                for row in rows:
                    name, weight, *_ = row
                    if name and weight is not None:
                        self.scoreboard[name] = int(weight)
        except Exception as e:
            print('Fail to load "{self.filename}":', e)

    def write_scoreboard(self):
        print(f'Writing scoreboard to "{self.filename}"')
        with open(self.filename, 'w') as _file:
            _writer = csv.writer(_file, delimiter=' ', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            _writer.writerows(sorted(self.scoreboard.items(), key=lambda x: (-x[1], x[0])))

    def open(self):
        if not self.opened:
            self.read_scoreboard()
            self.opened = True
            self.participants = set()

    def reopen(self):
        if not self.opened:
            self.opened = True

    def close(self):
        if self.opened:
            self.write_scoreboard()
            self.opened = False
            print("=" * 20)
            print(*self.participants)
            print("=" * 20)

    def winner(self):
        if self.opened:
            print('Close giveaway to pick a winner')
            return

        if not self.participants:
            print('No participants')
            return

        _participants = list(self.participants)
        _weights = [self.scoreboard.get(name, 0) for name in _participants]

        winner_name, *_ = random.choices(_participants, _weights)

        self.scoreboard[winner_name] = 0
        self.participants.discard(winner_name)
        self.write_scoreboard()

        return winner_name

    def add(self, name):
        if not self.opened:
            return
        if name in self.participants:
            return

        self.participants.add(name)
        if name in self.scoreboard:
            self.scoreboard[name] += 1
        else:
            self.scoreboard[name] = 1


class Bot(commands.Bot):
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('settings.ini')

        self.TMI_TOKEN = config['bot']['TMI_TOKEN']
        self.BOT_NICK = config['bot']['BOT_NICK']
        self.CHANNEL = config['bot']['CHANNEL']
        self.BOT_PREFIX = config['bot'].get('BOT_PREFIX', '!')
        self.ADMIN = config['bot']['ADMIN']

        super().__init__(
            irc_token=self.TMI_TOKEN,
            nick=self.BOT_NICK,
            prefix=self.BOT_PREFIX,
            initial_channels=[self.CHANNEL],
        )

    def is_admin(self, user):
        return user.name == self.ADMIN

    async def event_ready(self):
        self.giveaway = Giveaway()
        self.giveaway.read_scoreboard()
        print(f'== Bot {self.nick} ready ==')

    async def event_message(self, message):
        print(message.content[:120])
        await self.handle_commands(message)

    @commands.command(name='open', aliases=['o'])
    async def open_command(self, ctx):
        if self.is_admin(ctx.author):
            if not self.giveaway.opened:
                self.giveaway.open()
                await ctx.send_me(f'== Giveaway is opened == Type !giveaway to participate')

    @commands.command(name='reopen', aliases=['reo'])
    async def reopen_command(self, ctx):
        if self.is_admin(ctx.author):
            if not self.giveaway.opened:
                self.giveaway.reopen()
                await ctx.send_me(f'== Giveaway is RE-opened == Harry up! Type !giveaway to participate')

    @commands.command(name='close', aliases=['c'])
    async def close_command(self, ctx):
        if self.is_admin(ctx.author):
            if self.giveaway.opened:
                self.giveaway.close()
                await ctx.send_me(f'== Giveaway is closed == Pick the winner')

    @commands.command(name='winner', aliases=['w'])
    async def winner_command(self, ctx):
        if self.is_admin(ctx.author):
            winner = self.giveaway.winner()
            if winner is not None:
                await ctx.send_me(f'== The winner is @{winner} ==')
            else:
                await ctx.send_me(f'== No participants ==')

    @commands.command(name='giveaway', aliases=['ga'])
    async def giveaway_command(self, ctx):
        self.giveaway.add(ctx.author.name)

    @commands.command(name='scoreboard', aliases=['sb'])
    async def scoreboard_command(self, ctx):
        if self.is_admin(ctx.author):
            sb = ' '.join([
                f'{name} {score}' 
                for name, score in self.giveaway.scoreboard.items()
                if score > 0
            ])
            if len(sb) > 200:
                sb = sb[:200] + '...'
            await ctx.send(f'== Luck factor == {sb}')

    async def event_command_error(self, ctx, error):
        print(f'Error: {error}')


if __name__ == "__main__":
    bot = Bot()
    bot.run()
