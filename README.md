# twitch-giveaway-chatbot
Twitch giveaway chatbot with fair randomization

```
!open 
  [only-admin]
   drop participation list to empty and read scores from file scoreboard.txt

!reopen 
  [only-admin]
   just reopen giveaway if it's closed 

!close 
  [only-admin]
  stop getting new participators and save scoreboard to scoreboard.txt

!scoreboard
  [only-admin]
  for debug; returns scores (aka luck factors)

!winner 
  [only-admin]
  pick winner; yell nickname in chat; set score to 0; save scoreboard file; remove from current giveaway participant list (so if list is empty next !winner will return 'no party' and will do nothing)

!giveaway 
  [everyone]
  only accepts if giveaway's opened
```

# install and run

Download
Rename `settings.ini.sample` to `settings.ini`
Edit `settings.ini`
```
pip install -r requirements.txt
python3 bot.py
```
