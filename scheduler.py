import urllib

import schedule
import time
import requests
from config import settings
import urllib.parse

def send_emails():
    url = f"http://localhost:{settings.app_port}/send-emails?token={urllib.parse.quote(settings.auth_token)}"
    response = requests.get(url)
    print(response.json())


def send_platform_messages():
    print("calling send_platform_messages()")
    url = f"http://localhost:{settings.app_port}/send-to-platforms?token={urllib.parse.quote(settings.auth_token)}"
    response = requests.get(url)
    print(response.json())


def main():
    # Schedule the daily task to run at a specific time every day
    schedule.every().day.at("12:00").do(send_emails)

    # Schedule the hourly task to run every hour
    schedule.every().hour.do(send_platform_messages)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
