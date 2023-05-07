from datetime import datetime

from pydantic import BaseSettings
from fastapi_mail import ConnectionConfig, FastMail


class Settings(BaseSettings):
    app_url: str = "http://ensify.world"
    app_port: int = 8000
    auth_token = "6O9@YtAJhkbF5dAnA#fKJA%aGBfsCExJ"  # this token is used in scheduler calls
    items_per_user: int = 50
    mail_conf = ConnectionConfig(
        MAIL_USERNAME="no-reply@ensify.world",
        MAIL_PASSWORD="mYO9*6O$At1sL9rIDWIbEXBWrM6B7byq",
        MAIL_FROM="no-reply@ensify.world",
        MAIL_PORT=587,
        MAIL_SERVER="mail.ensify.world",
        MAIL_FROM_NAME="ENS Notify",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True
    )
    ens_offchain_proposals: dict = {
        "limit": 20,
        "url": "https://hub.snapshot.org/graphql"
    }
    ens_onchain_proposals: dict = {
        "limit": 10,
        "url": "https://api.thegraph.com/subgraphs/name/messari/ens-governance"
    }
    # https://core.telegram.org/bots#how-do-i-create-a-bot
    telegram_bot_token: str = "6031329135:AAG0uK936fyDVvScqIC7n-xXc8bE2KEnKqM"
    telegram_channel_names: dict = {
        "onchain": "@ENSProposals",
        "offchain": "@ENSProposals2",
        "calendar": "@ENSCalendar"
    }
    # https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks
    discord_channels: dict = {
        "onchain": "https://discord.com/api/webhooks/1104406424160833687/uRc4t466o_nufhsh6DLAqASG-Ze21CclP3-qWE-JeWhCahqpl7HRDUmBzaiFjYgvjkS0",
        "offchain": "https://discord.com/api/webhooks/1104408632990384239/MNy_-20fzTTIHXT1ard7psA4qHSERfUswP-VDjM36Mflk44AxOf04sVtlz6vyilAg0W_",
        "calendar": "https://discord.com/api/webhooks/1104421109199274037/AC8ULG7fVciIyuH_E3cXeabXqR1nCQJhzMqkV-hyJl3sM8D2zYYoEdsa3GpX6s0Cqac1"
    }
    fast_mail = FastMail(mail_conf)
    GOOGLE_API_KEY = "AIzaSyBFMDVHQ3pV2cA9BjeW_Yltm3bMff3MJWE"  # create one like: https://stackoverflow.com/a/27213635
    GOOGLE_CALENDAR_ID = "8im77u2b3euav0qjc067qb00ic@group.calendar.google.com"  # public calendar ID
    GOOGLE_CALENDAR_START_TIME = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'  # Get Events from this date
    GOOGLE_CALENDAR_MAX_RESULTS = 10  # maximum events should be fetched
    GOOGLE_CALENDAR_URL = f"https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events?key={GOOGLE_API_KEY}" \
                          f"&maxResults={GOOGLE_CALENDAR_MAX_RESULTS}&timeMin={GOOGLE_CALENDAR_START_TIME}"


settings = Settings()
