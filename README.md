# twitch-giveaway-chatbot
Twitch giveaway chatbot with increasing luck for every giveaway a user participates in but does not win.
Subscribers receive additional luck depending on their subscription tier. The amount of luck can be changed in the config.
Optionally sends giveaway reminders to chat and punishes user who participate but won't claim the prize.
The bot requires a TMI token, an Access token and your client ID.

```
!open 
  [admins only]
  Opens a giveaway. Chat users can join with !giveaway
 
!open word
  [admins only]
  Opens a giveaway with the word as a keyword. !giveaway does not work when using this.

!reopen 
  [admins only]
  Just reopen giveaway with the same keyword or ! gievaway if it's closed 

!close 
  [admins only]
  Stop getting new participants and save scoreboard to scoreboard.txt

!winner 
  [admins only]
  Picks a winner and announces them in chat, removes them from the giveaway, saves the scoreboard for all participating users.
  If called additional times the last user gets punished for not claiming their prize and a new winner is announced.

!confirm
  [admins only]
  Confirms the last winner and reset their luck to 0. This is done automatically when a giveaway is opened.

!bump @user n
  [admins only]
  Increases a users luck by n times the standard luck increase (see settings.ini).
  By default this adds n percentage points, eg '!bump user 5' would increase the users luck from 0 -> 5% or 43 -> 48%
  
!ignorelist
  [admins only]
  Prints the currently ignored users to the bot console.
  
!ignore @user
  [admins only]
  Adds a user to the ignorelist
  
!clear @user
  [admins only]
  Removes a user from the ignorelist
  
!scoreboard
  [admins only]
  Prints the current scoreboard to the bot console.

!me
  [everyone]
  Checks if self is in the current giveaway

!giveaway 
  [everyone]
  Only accepts if a giveaway is opened without a keyword.
  If no giveaway is opened the bot tells the chat

!stats
  [everyone]
  Gets the users stats: current luck, subscriber luck, lifetime entries and entires since last win.
```

# Install and run

*Requires python 3.7 or above. Developed on python 3.7.*
* Download
* Rename `settings.ini.sample` to `settings.ini`
* Edit `settings.ini`

Run commands below in cmd / powershell / WSL / Terminal in the folder. (Shift + Right-click in the folder on windows.)
```
pip install -r requirements.txt
python3 bot.py
```
