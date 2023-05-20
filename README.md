# ENSify

ENSify is a notification system for [ENS Domains](https://ens.domains/) proposals and meetings. It enables participants to receive notifications via email, Discord, and Telegram.

## Features

* Sends both offchain and onchain proposal reminders
* Reads Google Calendar for meetings updates
* Fully automated Discord and Telegram channels
* Selective email subscription
* Fast minimal web app

## Demo
ENSify demo is up at
[https://ensify.world](https://ensify.world/)

Video demo is at
[https://youtu.be/5bsi-g_NXAM](https://youtu.be/5bsi-g_NXAM)

## Quickstart with Docker

To run the application with Docker, first set the config file and then build the image and run it using Docker Compose. 

1. Clone the repository.
2. Copy [config_sample.py](config_sample.py) to a new file
named `config.py` and fill in the missing values.
3. Build the image:
   ```
   docker compose build
   ```

4. Run the image:
   ```
   docker compose up -d
   ```

By default, the application will be accessible on port 8000. If you want to use a different port, modify the `docker-compose.yml` file accordingly.

Once the image is built and running, you can access the application using the configured port.


## Without Docker

### Requirements

To run ENSify, make sure you have Python 3.6 or a higher
version installed on your system. To install the
dependencies you need `pip`.

### Installation

1- Clone the repository.

2- To install the required dependencies, 
run the following command:

```
pip install -r requirements.txt
```

### Configuration

Copy [config_sample.py](config_sample.py) to a new file
named `config.py` and fill in the missing values.

### Running

1- Run the main web app:

`python main.py`

2- Run the scheduler in parallel (i.e. separate terminal):

`python scheduler.py`

Make sure to keep both processes running for the system
to work correctly.

That's it! ENSify is now up and running, ready to send 
notifications for ENS Domains proposals and meetings.
