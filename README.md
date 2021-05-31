# twitch-giveaway-chatbot
Twitch giveaway chatbot with increasing luck for every giveaway a user participates in but does not win.
Subscribers receive additional luck depending on their subscription tier. THe amount of luck can be changed in the config.
The bot requires a TMI token, an Access token and your client ID.

```
!open 
  [only admin]
  opens a giveaway. Chat users can join with !giveaway
 
!open word
  [only admin]
  opens a giveaway with the word as a keyword. !giveaway does not work when using this.

!reopen 
  [only admin]
  just reopen giveaway if it's closed 

!close 
  [only admin]
  stop getting new participants and save scoreboard to scoreboard.txt

!winner 
  [only admin]
  pick winner; yell nickname in chat; save scoreboard file; remove from current giveaway participant list (so if list is empty next !winner will return 'no party' and will do nothing)

!confirm
  [only admin]
  confirms the last winner and reset their luck to 0. This is done automatically when a giveaway is opened.

!bump @user n
  [only admin]
  increases a users luck by n times the standard luck increase (see settings.ini).
  By default this adds n percentage points, eg '!bump user 5' would increase the users luck from 0 -> 5% or 43 -> 48%
  
!ignorelist
  [admin only]
  prints the currently ignored users to the bot console.
  
!scoreboard
  [admin only]
  prinst the current scoreboard to the bot console.

!me
  [everyone]
  checks if self is in the current giveaway

!giveaway 
  [everyone]
  only accepts if giveaway's opened

!stats
  [everyone]
  gets the users stats, current luck, subscriber luck and lifetime entries.
```

# install and run

* Download
* Rename `settings.ini.sample` to `settings.ini`
* Edit `settings.ini`

```
pip install -r requirements.txt
python3 bot.py
```
