# Telegram Similar Channel Parser

![](https://telegra.ph/file/10563cbc7e02f89d7fa7d.png)

So basic script, about 100 code lines, simple to use.

### How do you use it?

1. Download and install python 3.10+. [click](https://www.python.org/downloads/release/python-3115/)
2. Download/clone this repository (folder).
3. Open terminal and run command like this:

    `cd /path/to/this/folder`

4. Install required packages:

    `python -m pip install -r requirements.txt`

5. Copy `.env.example` to `.env` and add your Telegram credentials.

6. Run the script by this command:

    `python main.py`

### Running as a Telegram bot

1. Copy `.env.example` to `.env` and fill in `BOT_TOKEN`,
   `TELEGRAM_API_ID`, and `TELEGRAM_API_HASH`.
2. Start the bot with:

    `python bot.py`

The bot supports `/start` and `/help` for instructions.
Use `/parse <channel>` to begin parsing. The bot will show a short
"collecting" message, delete it when done, and then send you the results.
It also echoes any text you send and logs the received message.
Log messages are printed to the console so you can follow the process.

Enjoy.

### How to merge all parsed channels without duplicates?

1. Run this module:

    `python merge_parsed.py`
