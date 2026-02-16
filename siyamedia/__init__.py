# Authored By Certified Coders © 2025
from siyamedia.core.bot import MusicBotClient
from siyamedia.core.dir import StorageManager
from siyamedia.core.git import git
from siyamedia.core.userbot import Userbot
from siyamedia.misc import dbb, heroku

from .logging import LOGGER

StorageManager()
git()
dbb()
heroku()

app = MusicBotClient()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
