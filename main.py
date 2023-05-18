import enum
import uuid
from datetime import datetime
from typing import List, Annotated

import httpx
import requests
import telegram
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Form, Request
from fastapi_mail import FastMail, MessageSchema, MessageType
from pydantic import EmailStr, BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Enum as EnumColumn, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from starlette.background import BackgroundTasks
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from discord_webhook import DiscordEmbed, DiscordWebhook
from config import settings
from starlette.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


class EmailSchema(BaseModel):
    email: List[EmailStr]


fast_mail = FastMail(settings.mail_conf)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# define the database connection
SQLALCHEMY_DATABASE_URL = "sqlite:///./subscriptions.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app.mount("/assets", StaticFiles(directory="assets"), name="static")


@app.get("/")
async def read_index():
    return FileResponse('./assets/index.html')


# Define the custom dependency
def authenticate(token: str):
    if token != settings.auth_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return True


# define the SQLAlchemy models
class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    token = Column(String, unique=True)
    verified = Column(Boolean, default=False)
    offchain = Column(Boolean, default=False)
    onchain = Column(Boolean, default=False)
    calendar = Column(Boolean, default=False)


class ContentType(enum.Enum):
    offchain = "offchain"
    onchain = "onchain"
    calendar = "calendar"


class WaitingList(Base):
    __tablename__ = "waiting_list"
    id = Column(Integer, primary_key=True, index=True)
    content_type = Column(EnumColumn(ContentType))
    sent = Column(Boolean, default=False)
    content = Column(String)
    created = Column(Date, default=datetime.now)


class Platform(enum.Enum):
    telegram = "telegram"
    discord = "discord"
    email = "email"


class PlatformsSentList(Base):
    __tablename__ = "platforms_sent"
    id = Column(Integer, primary_key=True)
    content_id = Column(String, index=True)
    platform = Column(EnumColumn(Platform))
    content_type = Column(EnumColumn(ContentType))
    created = Column(Date, default=datetime.now)


# create the database tables
Base.metadata.create_all(bind=engine)


# define the Pydantic models
class SubscriptionCreate(BaseModel):
    email: str
    offchain: bool
    onchain: bool
    calendar: bool


class SubscriptionToken(BaseModel):
    token: str


class OffchainProposal(BaseModel):
    id: str
    ipfs: str
    link: str
    title: str
    body: str
    choices: list
    created: int
    start: int
    end: int
    state: str
    author: str
    type: str
    app: str
    space: dict


class OnchainProposal(BaseModel):
    id: str
    txnHash: str
    state: str
    creationTime: int
    executionTime: int
    description: str


async def get_offchain_proposals():
    query = '''
        query Proposals {
          proposals (''' + f'first: {settings.ens_offchain_proposals["limit"]},' + '''
            skip: 0,
            # where: {
            #   space_in: ["yam.eth"],
            #   state: "closed"
            # },
            orderBy: "created",
            orderDirection: desc
          ) {
            id
            ipfs
            link
            title
            body
            choices
            created
            start
            end
            state
            author
            type
            app
            space {
              id
              name
            }
          }
        }
    '''

    url = settings.ens_offchain_proposals["url"]

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={'query': query})

    response_data = response.json()['data']['proposals']

    proposals = [OffchainProposal(**proposal_data) for proposal_data in response_data]

    return proposals


async def get_onchain_proposals():
    query = '''
    {
        governanceFrameworks {
            name
            type
            contractAddress
            tokenAddress
        }
        governances {
            currentDelegates
            currentTokenHolders
            totalTokenSupply
        }
        proposals(''' + f'first: {settings.ens_onchain_proposals["limit"]}' + ''', orderBy: startBlock, orderDirection: desc) {
            id
            txnHash
            state
            creationTime
            executionTime
            description
        }
    }
    '''

    url = settings.ens_onchain_proposals["url"]

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={'query': query})

    response_data = response.json()['data']['proposals']

    proposals = [OnchainProposal(**proposal_data) for proposal_data in response_data]

    return proposals


@app.post("/subscribe/")
async def subscribe(request: Request, background_tasks: BackgroundTasks, email: Annotated[str, Form()] = None,
                    onChain: Annotated[bool, Form()] = False,
                    offChain: Annotated[bool, Form()] = False, calendar: Annotated[bool, Form()] = False):
    if (not email):
        return templates.TemplateResponse("message.html",
                                          {"request": request, "message": "Please enter your email address."})

    if (not (offChain or onChain or calendar)):
        return templates.TemplateResponse("message.html",
                                          {"request": request, "message": "You should select at least one checkbox."})

    subscription = Subscription(email=email, onchain=onChain, offchain=offChain, calendar=calendar)
    # generate a unique token for this subscription
    token = str(uuid.uuid4())

    # create a new Subscription object and save it to the database
    with SessionLocal() as db:
        if db.query(Subscription).filter_by(email=email).first():
            return templates.TemplateResponse("message.html",
                                              {"request": request,
                                               "message": "Already subscribed."})
        db_subscription = Subscription(email=subscription.email, onchain=subscription.onchain,
                                       offchain=subscription.offchain, calendar=subscription.calendar, token=token)
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)

    # send a verification email to the subscriber
    send_verification_email(subscription.email, token, background_tasks)

    return templates.TemplateResponse("message.html",
                                      {"request": request,
                                       "message": "Verification email has been sent, don't forget to check spams."})


@app.get("/unsubscribe/{token}")
async def unsubscribe(request: Request, token: str):
    # look up the subscription by its token
    with SessionLocal() as db:
        subscription = db.query(Subscription).filter_by(token=token).first()

        # if the subscription was found, delete it from the database
        if subscription is not None:
            db.delete(subscription)
            db.commit()
            return templates.TemplateResponse("message.html",
                                              {"request": request, "message": "Unsubscribed successfully."})

        # if the subscription was not found, raise an HTTPException
        return templates.TemplateResponse("message.html",
                                          {"request": request,
                                           "message": "Subscription not found or already unsubscribed."},
                                          status_code=404)


async def get_google_calendar_events():
    try:
        response = requests.get(settings.GOOGLE_CALENDAR_URL)
        events_result = response.json()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return []

        return events

    except requests.exceptions.RequestException as error:
        print('An error occurred: %s' % error)


@app.get("/verify/{token}")
async def verify(request: Request, token: str, background_tasks: BackgroundTasks):
    # look up the subscription by its token
    with SessionLocal() as db:
        subscription = db.query(Subscription).filter_by(token=token).first()

        # if the subscription was not found, raise an HTTPException
        if subscription is None:
            return templates.TemplateResponse("message.html",
                                              {"request": request, "message": "Subscription not found."},
                                              status_code=404)

            # if the subscription has already been verified, return a message indicating this
        if subscription.verified:
            send_unsubscibe_link_email(subscription.email, token, background_tasks)
            return templates.TemplateResponse("message.html",
                                              {"request": request, "message": "Subscription already verified."})
        # set the subscription as verified and update the database
        subscription.verified = True
        db.commit()

    return templates.TemplateResponse("message.html", {"request": request, "message": "Subscription verified."})


# define the function to send verification emails
def send_verification_email(email, token, background_tasks: BackgroundTasks):
    message = MessageSchema(
        subject="Verify your email subscription",
        recipients=[email],
        body=f'To confirm your subscription, click this link: {settings.app_url}/verify/{token}',
        subtype=MessageType.plain)
    background_tasks.add_task(fast_mail.send_message, message)


def send_unsubscibe_link_email(email, token, background_tasks: BackgroundTasks):
    message = MessageSchema(
        subject="Email verified.",
        recipients=[email],
        body=f'Your email is verified. You will receive ENS notifications daily.\n'
             f'If you needed to unsubscribe at any time, here is the link: {settings.app_url}/unsubscribe/{token}',
        subtype=MessageType.plain)

    background_tasks.add_task(fast_mail.send_message, message)


def mark_as_sent(db_object: PlatformsSentList):
    with SessionLocal() as db:
        db.add(db_object)
        db.commit()
        db.refresh(db_object)


def add_to_waiting_list(db_object: PlatformsSentList, waiting_object: WaitingList):
    with SessionLocal() as db:
        db.add(waiting_object)
        db.add(db_object)
        db.commit()
        db.refresh(db_object)


def set_waiting_as_sent(content_type: ContentType):
    with SessionLocal() as db:
        db.query(WaitingList).filter_by(content_type=content_type).update({WaitingList.sent: True})
        db.commit()


async def send_telegram_message(channel, message, db_object: PlatformsSentList):
    url = f'https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage'
    data = {'chat_id': channel, 'text': message, 'parse_mode': 'Markdown'}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, data=data)
        try:
            response.raise_for_status()
            mark_as_sent(db_object)
        except:
            print(f"exception for channel {channel} on message:\n{message}")
            print("\n\n\nresponse json\n", response.json())
        return response.json()


def send_to_discord(title: str, description: str, footer: str, webhook_url: str, db_object: PlatformsSentList):
    try:
        webhook = DiscordWebhook(
            url=webhook_url
        )
        webhook.add_embed(DiscordEmbed(description=description, title=title))
        if footer:
            webhook.add_embed(DiscordEmbed(description=footer))
        webhook.execute()
        mark_as_sent(db_object)
    except KeyError:
        print("Error or retry later")
    except Exception as e:
        print("[X] Discord Error:\n>", e)


@app.get("/send-to-platforms")
async def send_platform_updates(
        background_tasks: BackgroundTasks, auth: bool = Depends(authenticate)) -> JSONResponse:
    await send_onchain(background_tasks)
    await send_offchain(background_tasks)
    await send_calendar(background_tasks)


async def send_onchain(
        background_tasks: BackgroundTasks) -> JSONResponse:
    await send_on_chain_proposals(background_tasks)
    return JSONResponse(status_code=200, content={"message": "on chain proposals has been sent"})


async def send_offchain(
        background_tasks: BackgroundTasks) -> JSONResponse:
    await send_off_chain_proposals(background_tasks)
    return JSONResponse(status_code=200, content={"message": "off chain proposals has been sent"})


async def send_calendar(
        background_tasks: BackgroundTasks) -> JSONResponse:
    await send_calendar_events(background_tasks)
    return JSONResponse(status_code=200, content={"message": "calendar events has been sent"})


@app.get("/send-emails")
async def send_emails(
        background_tasks: BackgroundTasks, auth: bool = Depends(authenticate)) -> JSONResponse:
    await send_onchain_emails(background_tasks)
    set_waiting_as_sent(content_type=ContentType.onchain)
    await send_offchain_emails(background_tasks)
    set_waiting_as_sent(content_type=ContentType.offchain)
    await send_calendar_events_emails(background_tasks)
    set_waiting_as_sent(content_type=ContentType.calendar)

    return JSONResponse(status_code=200, content={"message": "send emails initiated."})


async def send_onchain_emails(
        background_tasks: BackgroundTasks) -> JSONResponse:
    with SessionLocal() as db:
        waiting_elems = db.query(WaitingList).filter_by(content_type=ContentType.onchain, sent=False)
        on_chain_user_emails = db.query(Subscription).filter_by(onchain=True, verified=True)
    mail_content = ""
    for email in waiting_elems:
        mail_content = mail_content + email.content + "\n\n\n"
    if mail_content:
        for x in on_chain_user_emails:
            message = MessageSchema(
                subject="ENS Domains OnChain Proposals",
                recipients=[x.email],
                body=mail_content,
                subtype=MessageType.plain)
            background_tasks.add_task(fast_mail.send_message, message)


async def send_offchain_emails(
        background_tasks: BackgroundTasks) -> JSONResponse:
    with SessionLocal() as db:
        waiting_elems = db.query(WaitingList).filter_by(content_type=ContentType.offchain, sent=False)
        on_chain_user_emails = db.query(Subscription).filter_by(offchain=True, verified=True)
    mail_content = ""
    for email in waiting_elems:
        mail_content = mail_content + email.content + "\n\n\n"
    if mail_content:
        for x in on_chain_user_emails:
            message = MessageSchema(
                subject="ENS Domains Offchain Proposals",
                recipients=[x.email],
                body=mail_content,
                subtype=MessageType.plain)
            background_tasks.add_task(fast_mail.send_message, message)


async def send_calendar_events_emails(
        background_tasks: BackgroundTasks) -> JSONResponse:
    with SessionLocal() as db:
        waiting_elems = db.query(WaitingList).filter_by(content_type=ContentType.calendar, sent=False)
        on_chain_user_emails = db.query(Subscription).filter_by(calendar=True, verified=True)
    mail_content = ""
    for email in waiting_elems:
        mail_content = mail_content + email.content + "\n\n\n"
    if mail_content:
        for x in on_chain_user_emails:
            message = MessageSchema(
                subject="ENS Domains Calendar Events",
                recipients=[x.email],
                body=mail_content,
                subtype=MessageType.plain)
            background_tasks.add_task(fast_mail.send_message, message)


async def send_on_chain_proposals(background_tasks):
    proposals: List[OnchainProposal] = await get_onchain_proposals()
    for p in proposals:
        # look up the subscription by its token
        with SessionLocal() as db:
            if not db.query(PlatformsSentList).filter_by(content_id=p.id, platform=Platform.email,
                                                         content_type=ContentType.onchain).first():
                db_object = PlatformsSentList(content_id=p.id, platform=Platform.email,
                                              content_type=ContentType.onchain)
                waiting_object = WaitingList(content_type=ContentType.onchain,
                                             content=on_chain_proposals_mail_format(p))
                background_tasks.add_task(add_to_waiting_list, db_object, waiting_object)
            if not db.query(PlatformsSentList).filter_by(content_id=p.id, platform=Platform.telegram,
                                                         content_type=ContentType.onchain).first():
                # Send To Telegram
                tg_message = on_chain_proposals_telegram_format(p)
                db_object = PlatformsSentList(content_id=p.id, platform=Platform.telegram,
                                              content_type=ContentType.onchain)
                background_tasks.add_task(send_telegram_message, settings.telegram_channel_names['onchain'], tg_message,
                                          db_object)
            # Send To Discord
            if not db.query(PlatformsSentList).filter_by(content_id=p.id, platform=Platform.discord,
                                                         content_type=ContentType.onchain).first():
                d_title, d_description, d_footer = on_chain_proposals_discord_format(p)
                db_object = PlatformsSentList(content_id=p.id, platform=Platform.discord,
                                              content_type=ContentType.onchain)
                background_tasks.add_task(send_to_discord, d_title, d_description, d_footer,
                                          settings.discord_channels['onchain'], db_object)


async def send_off_chain_proposals(background_tasks):
    proposals: List[OffchainProposal] = await get_offchain_proposals()
    for p in proposals:
        # look up the subscription by its token
        with SessionLocal() as db:
            if not db.query(PlatformsSentList).filter_by(content_id=p.id, platform=Platform.email,
                                                         content_type=ContentType.offchain).first():
                db_object = PlatformsSentList(content_id=p.id, platform=Platform.email,
                                              content_type=ContentType.offchain)
                waiting_object = WaitingList(content_type=ContentType.offchain,
                                             content=off_chain_proposals_mail_format(p))
                background_tasks.add_task(add_to_waiting_list, db_object, waiting_object)

            if not db.query(PlatformsSentList).filter_by(content_id=p.id, platform=Platform.telegram,
                                                         content_type=ContentType.offchain).first():
                # Send To Telegram
                tg_message = off_chain_proposals_telegram_format(p)
                db_object = PlatformsSentList(content_id=p.id, platform=Platform.telegram,
                                              content_type=ContentType.offchain)
                background_tasks.add_task(send_telegram_message, settings.telegram_channel_names['offchain'],
                                          tg_message,
                                          db_object)
            # Send To Discord
            if not db.query(PlatformsSentList).filter_by(content_id=p.id, platform=Platform.discord,
                                                         content_type=ContentType.offchain).first():
                d_title, d_description, d_footer = off_chain_proposals_discord_format(p)
                db_object = PlatformsSentList(content_id=p.id, platform=Platform.discord,
                                              content_type=ContentType.offchain)
                background_tasks.add_task(send_to_discord, d_title, d_description, d_footer,
                                          settings.discord_channels['offchain'], db_object)


async def send_calendar_events(background_tasks):
    calendar_events = await get_google_calendar_events()
    for event in calendar_events:
        if event.get('status', '') != 'cancelled':
            with SessionLocal() as db:
                if not db.query(PlatformsSentList).filter_by(content_id=event.get('id'), platform=Platform.email,
                                                             content_type=ContentType.calendar).first():
                    db_object = PlatformsSentList(content_id=event.get('id'), platform=Platform.email,
                                                  content_type=ContentType.calendar)
                    waiting_object = WaitingList(content_type=ContentType.calendar,
                                                 content=calendar_mail_format(event))
                    background_tasks.add_task(add_to_waiting_list, db_object, waiting_object)
                if not db.query(PlatformsSentList).filter_by(content_id=event.get('id'), platform=Platform.telegram,
                                                             content_type=ContentType.calendar).first():
                    # Send To Telegram
                    tg_message = calendar_telegram_format(event)
                    db_object = PlatformsSentList(content_id=event.get('id'), platform=Platform.telegram,
                                                  content_type=ContentType.calendar)
                    background_tasks.add_task(send_telegram_message, settings.telegram_channel_names['calendar'],
                                              tg_message,
                                              db_object)
                # Send To Discord
                if not db.query(PlatformsSentList).filter_by(content_id=event.get('id'), platform=Platform.discord,
                                                             content_type=ContentType.calendar).first():
                    d_title, d_description, d_footer = calendar_discord_format(event)
                    db_object = PlatformsSentList(content_id=event.get('id'), platform=Platform.discord,
                                                  content_type=ContentType.calendar)
                    background_tasks.add_task(send_to_discord, d_title, d_description, d_footer,
                                              settings.discord_channels['calendar'], db_object)


def on_chain_proposals_telegram_format(proposal: OnchainProposal):
    return f"""
{telegram.helpers.escape_markdown(proposal.description[:3200], version=1)}
-----------------------------
*id*: "{proposal.id}"
*txnHash*: "{proposal.txnHash}"
*state*: "{proposal.state}"
*creationTime*: {proposal.creationTime}
*executionTime*: {proposal.executionTime}
            """


def on_chain_proposals_mail_format(proposal: OnchainProposal):
    return f"""
{proposal.description}
*id*: "{proposal.id}"
*txnHash*: "{proposal.txnHash}"
*state*: "{proposal.state}"
*creationTime*: {proposal.creationTime}
*executionTime*: {proposal.executionTime}
            """


def on_chain_proposals_discord_format(proposal: OnchainProposal):
    description = proposal.description[:2000]
    footer = f"""
*id*: "{proposal.id}"
*txnHash*: "{proposal.txnHash}"
*state*: "{proposal.state}"
*creationTime*: {proposal.creationTime}
*executionTime*: {proposal.executionTime}
"""[:2000]
    title = "Proposal"
    return title, description, footer


def off_chain_proposals_telegram_format(proposal: OffchainProposal):
    return f"""
*{telegram.helpers.escape_markdown(proposal.title)}* _(state:{proposal.state})_
*space*: {proposal.space.__repr__()} ,*type*: {proposal.type}
*app*: {proposal.app}, *author*: {proposal.author}      
*start*: {proposal.start} ,*end*: {proposal.end} ,*created*: {proposal.created}

{telegram.helpers.escape_markdown(proposal.body[:3100])}
*choices*: {''.join(proposal.choices)[:500]} 
--------
*ipfs*: {proposal.ipfs}
*link*: {proposal.link}
*id*: {proposal.id}
            """[:4000]


def off_chain_proposals_mail_format(proposal: OffchainProposal):
    return f"""
*{proposal.title}* _(state:{proposal.state})_
*space*: {proposal.space.__repr__()} ,*type*: {proposal.type}
*app*: {proposal.app}, *author*: {proposal.author}      
*start*: {proposal.start} ,*end*: {proposal.end} ,*created*: {proposal.created}
{proposal.body}
*choices*: {''.join(proposal.choices)} 
--------
*ipfs*: {proposal.ipfs}
*link*: {proposal.link}
*id*: {proposal.id}
            """


def off_chain_proposals_discord_format(proposal: OffchainProposal):
    description = proposal.body[:2000]
    footer = f"""
*choices*: {proposal.choices} 
*ipfs*: {proposal.ipfs}
*link*: {proposal.link}
*id*: {proposal.id}
    """[:2000]
    title = f"*{proposal.title}* _(state:{proposal.state})_"
    return title, description, footer


def calendar_mail_format(event: dict):
    return f"""
{event.get('summary')} _(Status: {event.get('status')})_
Start: {event.get('start', {}).get('dateTime')} (timeZone:{event.get('start', {}).get('timeZone')})
End: {event.get('end', {}).get('dateTime')} (timeZone:{event.get('end', {}).get('timeZone')})
Event Link: {event.get('htmlLink').replace("/calendar/event?eid=", "/calendar/u/0/r/eventedit/copy/")}
hangoutLink: {event.get('hangoutLink')}
        """


def calendar_telegram_format(event: dict):
    return f"""
{event.get('summary')} _(Status: {event.get('status')})_
Start: {event.get('start', {}).get('dateTime')} (timeZone:{event.get('start', {}).get('timeZone')})
End: {event.get('end', {}).get('dateTime')} (timeZone:{event.get('end', {}).get('timeZone')})
Event Link: {event.get('htmlLink').replace("/calendar/event?eid=", "/calendar/u/0/r/eventedit/copy/")}
hangoutLink: {event.get('hangoutLink')}
        """


def calendar_discord_format(event: dict):
    title = f"{event.get('summary')} _(Status: {event.get('status')})_"
    description = f"""
Start: {event.get('start', {}).get('dateTime')} (timeZone:{event.get('start', {}).get('timeZone')})
End: {event.get('end', {}).get('dateTime')} (timeZone:{event.get('end', {}).get('timeZone')})
Event Link: {event.get('htmlLink').replace("/calendar/event?eid=", "/calendar/u/0/r/eventedit/copy/")}
hangoutLink: {event.get('hangoutLink')}
        """
    return title, description, None


# run the app
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.app_port)
