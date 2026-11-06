"""Write a local, ignored bot configuration. Does not send messages."""
from pathlib import Path
from getpass import getpass
import json

def main():
    token=getpass('Telegram bot token from BotFather (hidden): ').strip()
    if not token or ':' not in token:raise SystemExit('Token format is invalid; configuration was not written.')
    path=Path(__file__).resolve().parents[1]/'.secrets/telegram/config.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'token':token,'chat_id':''}),encoding='utf-8')
    print('Saved locally. Send /start to your bot to subscribe. No token is printed or added to Git.')

if __name__=='__main__':main()
