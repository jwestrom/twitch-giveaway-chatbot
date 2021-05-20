import csv
import os
from typing import Dict

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

class Scoreboard:
    _filename: str
    _scoreboard: Dict[str, User]

    def __init__(self, filename=None):
        self._filename = filename or 'scoreboard.txt'
        self._scoreboard = {}

    # Load the scoreboard from a file.
    def load(self):

        if not os.path.isfile(self._filename):
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
            print(f'Fail to load "{self._filename}":', e)

        for user in scoreboard.items():
            print(f'Scoreboard: {user.name} {user.luck}')

    # Save the scoreboard to a file.
    def save(self):

        with open(self._filename, 'w', newline='') as _file:
            _writer = csv.writer(_file, delimiter=' ', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            rows = []
            for _, user in self._scoreboard.items():
                print(user.toCsv())
                rows.append(user.toCsv())
            _writer.writerows(rows)

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
        if name in self._scoreboard:
            user = self._scoreboard.get(name)
            user.luck = user.luck + 1
            user.tier = tier
            user.lifetime = user.lifetime + 1
            self._scoreboard[name] = user
        else:
            self._scoreboard[name] = User(name, luck=1, tier=tier, lifetime=1)

    def bump(self, name: str, points: int) -> None:
        if name in self._scoreboard:
            self._scoreboard[name].luck = self._scoreboard[name].luck + points

def main():
    sc = Scoreboard('score.txt')
    sc.add('brad', 3)
    sc.add('laddden', 0)
    sc.save()

if __name__ == "__main__":
    main()