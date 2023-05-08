from datetime import datetime

from pydantic import BaseSettings
from fastapi_mail import ConnectionConfig, FastMail


class Settings(BaseSettings):
    app_url: str = "https://domain.com"
    app_port: int = 8000
    auth_token = "[Put your token here, any string is accepted]"  # this token is used in scheduler calls
    items_per_user: int = 50
    mail_conf = ConnectionConfig(
        MAIL_USERNAME="[mail@domain.com]",
        MAIL_PASSWORD="[password]",
        MAIL_FROM="[mail@domain.com]",
        MAIL_PORT=587,
        MAIL_SERVER="[mail.domain.com]",
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
    telegram_bot_token: str = "[your telegram bot token]"
    telegram_channel_names: dict = {
        "onchain": "[@telegram_channel_username]",
        "offchain": "[@telegram_channel_username2]",
        "calendar": "[@telegram_channel_username3]"
    }
    # https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks
    discord_channels: dict = {
        "onchain": "https://discord.com/api/webhooks/[your discord webhook token]",
        "offchain": "https://discord.com/api/webhooks/[your discord webhook token]",
        "calendar": "https://discord.com/api/webhooks/[your discord webhook token]"
    }
    fast_mail = FastMail(mail_conf)
    GOOGLE_API_KEY = "[Google app API key]"  # create one like: https://stackoverflow.com/a/27213635
    GOOGLE_CALENDAR_ID = "8im77u2b3euav0qjc067qb00ic@group.calendar.google.com"  # ENS public calendar ID
    GOOGLE_CALENDAR_START_TIME = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'  # Get Events from this date
    GOOGLE_CALENDAR_MAX_RESULTS = 10  # maximum events should be fetched
    GOOGLE_CALENDAR_URL = f"https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events?key={GOOGLE_API_KEY}" \
                          f"&maxResults={GOOGLE_CALENDAR_MAX_RESULTS}&timeMin={GOOGLE_CALENDAR_START_TIME}"


settings = Settings()
