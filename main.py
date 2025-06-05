import asyncio
import os
import sys
from pathlib import Path
import re  # Added for parsing usernames
import csv  # Added for CSV output

from loguru import logger
from telethon import TelegramClient, functions, types
from yarl import URL

import config

logger.remove()
logger.add(
    sink=sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> - <level>{message}</level>",
)

# --- Topic Keywords (Example) ---
# You can expand this dictionary with more topics and keywords
TOPIC_KEYWORDS = {
    "Криптовалюты/Финансы": [
        "крипт", "crypto", "p2p", "трейд", "инвест", "финанс",
        "binance", "бинанс", "trade", "invest", "finance",
        "nft", "нфт", "usdt", "btc", "eth"
    ],
    "Новости/Медиа": [
        "новост", "news", "сми", "медиа", "media", "журнал"
    ],
    "Технологии/IT": [
        "tech", "техно", "it", "айти", "разработ", "программ",
        "dev", "код", "code"
    ],
    "Маркетинг/Бизнес": [
        "маркет", "бизнес", "business", "реклам", "пиар",
        "pr", "продаж", "sale"
    ],
    "Образование": [
        "образ", "обучен", "курс", "урок", "школа",
        "school", "educat"
    ],
    # Add more topics and keywords here
}


def get_channel_topic(title: str) -> str:
    """
    Determines channel topic based on keywords in the title.
    """
    if not title:
        return "Не определена"

    title_lower = title.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            try:
                # Use word boundaries to avoid partial matches
                if re.search(r"\b" + re.escape(keyword) + r"\b", title_lower):
                    return topic
            except re.error:
                # Fallback to simple substring check if regex fails
                if keyword in title_lower:
                    return topic

    return "Не определена"


# --- Helper functions for parsing config.LINE_FORMAT lines ---


def build_regex_pattern(format_string: str) -> str:
    """
    Builds a regex pattern to parse lines based on the format string.
    """
    # 1. Escape the format string so that delimiters are literal
    pattern_str = re.escape(format_string)
    # 2. Replace escaped placeholders with named regex capture groups
    pattern_str = pattern_str.replace(r"\{username\}", r"(?P<username>[\w]+)")
    pattern_str = pattern_str.replace(r"\{participants_count\}", r"(?P<participants_count>\d*)")
    pattern_str = pattern_str.replace(r"\{title\}", r"(?P<title>.*)")
    # Replace any other potential generic placeholders with a wildcard
    pattern_str = re.sub(r"\\\{.*?\\\}", r".*?", pattern_str)
    # Add anchors to match the whole line
    return f"^{pattern_str}$"


def parse_username_from_line(line: str, format_string: str) -> str | None:
    """
    Parses the username from a line formatted according to config.LINE_FORMAT.
    Returns the 'username' group or None if no match.
    """
    try:
        pattern = build_regex_pattern(format_string)
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            return match.group("username")
        return None
    except re.error as e:
        logger.error(f"Regex error parsing username from line '{line}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in parse_username_from_line: {e}")
        return None


def parse_line_to_dict(line: str, format_string: str) -> dict | None:
    """
    Parses a line formatted according to config.LINE_FORMAT into a dictionary:
    { 'username': str, 'participants_count': int, 'title': str }
    """
    try:
        pattern = build_regex_pattern(format_string)
        match = re.match(pattern, line, re.IGNORECASE | re.DOTALL)
        if match:
            data = {
                "username": match.group("username") or None,
                "participants_count": match.group("participants_count") or "0",
                "title": match.group("title") or "N/A"
            }
            try:
                data["participants_count"] = int(data["participants_count"])
            except (ValueError, TypeError):
                data["participants_count"] = 0
            return data
        return None
    except re.error as e:
        logger.error(f"Regex error parsing line to dict '{line}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in parse_line_to_dict: {e}")
        return None


# --- End of helper functions ---


class SimilarChannelParser:
    def __init__(self):
        proxy = getattr(config, "PROXY", None)
        if proxy:
            proxy_url = URL(proxy)
            proxy = {
                "proxy_type": proxy_url.scheme,
                "username": proxy_url.user,
                "password": proxy_url.password,
                "addr": proxy_url.host,
                "port": proxy_url.port,
            }

        session_folder = Path("sessions")
        session_folder.mkdir(exist_ok=True)

        self.client = TelegramClient(
            session=os.path.join(session_folder.name, "account"),
            api_id=config.TELEGRAM_API_ID,
            api_hash=config.TELEGRAM_API_HASH,
            proxy=proxy,
            device_model=config.TELEGRAM_DEVICE_MODEL,
            system_version=config.TELEGRAM_SYSTEM_VERSION,
            app_version=config.TELEGRAM_APP_VERSION,
            lang_code="en",
            system_lang_code="en",
        )
        self.is_connected = False

    async def connect(self, bot_token: str | None = None):
        """
        Connects the TelegramClient.
        If bot_token is provided, authorizes as a bot (no phone/code prompt).
        Otherwise, attempts user login (phone + code).
        """
        if not self.is_connected:
            logger.info("Connecting to Telegram...")
            try:
                if not self.client.is_connected():
                    await self.client.connect()

                if bot_token:
                    # Authorize as bot using bot_token
                    await self.client.start(bot_token=bot_token)
                    logger.info("Authorized as bot successfully.")
                else:
                    # Authorize as user
                    if not await self.client.is_user_authorized():
                        logger.info("First run or session expired: please log in (phone + code).")
                        await self.client.start()  # will prompt for phone+code
                        logger.info("User authorization successful.")
                self.is_connected = True
                logger.info("Telegram client connected successfully.")
            except Exception as e:
                logger.error(f"Failed to connect/authorize Telegram client: {e}")
                raise

    async def get_similar_channels(self, channel_entity: str) -> list[str]:
        """
        Fetches similar channels for a given channel_entity (username or link).
        Returns a list of formatted strings according to config.LINE_FORMAT.
        """
        if not self.is_connected:
            # By default, connect as bot if BOT_TOKEN is set
            if config.BOT_TOKEN:
                await self.connect(bot_token=config.BOT_TOKEN)
            else:
                await self.connect(bot_token=None)

        logger.info(f'Start parsing similar channels of "{channel_entity}"...')

        try:
            peer = channel_entity
            req = functions.channels.GetChannelRecommendationsRequest(channel=peer)
            res: types.messages.Chats = await self.client(req)
        except (ValueError, TypeError) as e:
            logger.error(f'Error fetching recommendations for "{channel_entity}": {e}')
            return []
        except (types.errors.ChannelPrivateError, types.errors.ChatAdminRequiredError) as e:
            logger.warning(f'Cannot access recommendations for "{channel_entity}": {e}')
            return []
        except types.errors.FloodWaitError as e:
            logger.warning(f"Flood wait for {channel_entity}: wait {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
            return []
        except Exception as e:
            logger.error(f'Unexpected error fetching recommendations for "{channel_entity}": {type(e).__name__} - {e}')
            return []

        channels: list[str] = []
        if not hasattr(res, "chats"):
            logger.warning(f"No 'chats' in response for {channel_entity}: {res}")
            return []

        for chat in res.chats:
            if (
                isinstance(chat, types.Channel)
                and getattr(chat, "username", None)
                and hasattr(chat, "participants_count")
                and hasattr(chat, "title")
            ):
                try:
                    channels.append(config.LINE_FORMAT.format(
                        username=chat.username,
                        participants_count=getattr(chat, "participants_count", 0),
                        title=getattr(chat, "title", "N/A"),
                    ))
                except KeyError as e:
                    logger.warning(f"Missing key {e} when formatting channel {chat.title}. Skipping.")
                except Exception as e:
                    logger.error(f"Error formatting channel {chat.title}: {e}. Skipping.")
            else:
                logger.warning(
                    f"Skipping item (not a full channel) for {getattr(chat, 'title', 'N/A')} (type: {type(chat)})"
                )

        count = getattr(res, "count", len(channels))
        log_text = f'Parsed {len(channels)}/{count if count else len(channels)} similar channels for "{channel_entity}".'
        if hasattr(res, "count") and len(channels) < res.count:
            log_text += f" You may need Telegram Premium to get all {res.count}."
        logger.success(log_text)
        return channels

    async def main(self):
        """
        Main function to handle CLI input (Level 1 and Level 2 parsing) if run standalone.
        """
        saving_dir_base = Path(config.SAVING_DIRECTORY)
        saving_dir_base.mkdir(exist_ok=True)

        if not saving_dir_base.is_dir():
            logger.error(
                f"Could not create/find directory {saving_dir_base}. Check permissions or change SAVING_DIRECTORY."
            )
            sys.exit(1)

        try:
            # Connect as user if BOT_TOKEN isn't provided
            if config.BOT_TOKEN:
                await self.connect(bot_token=config.BOT_TOKEN)
            else:
                await self.connect(bot_token=None)

            while True:
                channel_username_l0 = input(
                    "\nEnter initial channel username (e.g., @channelname or channelname; leave empty to exit): "
                ).strip()
                if not channel_username_l0:
                    logger.info("Exiting.")
                    break

                logger.info(f"--- Level 1 Parsing for: {channel_username_l0} ---")
                channels_l1 = await self.get_similar_channels(channel_username_l0)

                safe_filename_l0 = channel_username_l0.lstrip("@").replace("/", "_").replace("\\", "_")
                saving_file_l1 = (saving_dir_base / f"{safe_filename_l0}_level1").with_suffix(".txt")

                if not channels_l1:
                    logger.warning(f"No Level 1 results for {channel_username_l0}. Skipping Level 2.")
                    saving_file_l1.write_text("", encoding="utf-8")
                    logger.info(f"Created empty Level 1 file: {saving_file_l1}")
                    continue

                saving_file_l1.write_text("\n".join(channels_l1), encoding="utf-8")
                logger.success(f"Level 1: {len(channels_l1)} saved to {saving_file_l1}.")

                # Level 2 parsing
                logger.info(f"--- Level 2 Parsing for: {channel_username_l0} ---")
                level2_data_for_csv = []
                usernames_l1 = []
                for line in channels_l1:
                    username = parse_username_from_line(line, config.LINE_FORMAT)
                    if username:
                        usernames_l1.append(username)
                    else:
                        logger.warning(f"Could not extract username from '{line}'")

                if not usernames_l1:
                    logger.warning(f"No valid usernames for Level 2 from {channel_username_l0}.")
                    continue

                parsed_l2_count = 0
                total_l2_found = 0
                for i, channel_username_l1 in enumerate(usernames_l1, 1):
                    peer_l1 = channel_username_l1 if channel_username_l1.startswith("@") else f"@{channel_username_l1}"
                    logger.info(f"--- Level 2 ({i}/{len(usernames_l1)}): {peer_l1} ---")

                    channels_l2 = await self.get_similar_channels(peer_l1)
                    parsed_l2_count += 1
                    total_l2_found += len(channels_l2)

                    if channels_l2:
                        for line_l2 in channels_l2:
                            parsed_data = parse_line_to_dict(line_l2, config.LINE_FORMAT)
                            if parsed_data:
                                level2_data_for_csv.append({
                                    "source_l1": channel_username_l1,
                                    "found_l2_username": parsed_data.get("username", "N/A"),
                                    "found_l2_count": parsed_data.get("participants_count", 0),
                                    "found_l2_title": parsed_data.get("title", "N/A")
                                })
                            else:
                                logger.warning(f"Failed to parse L2 line: '{line_l2}'")
                    else:
                        logger.info(f"No L2 results for {peer_l1}.")

                    delay = getattr(config, "DELAY_BETWEEN_REQUESTS", 1.5)
                    logger.debug(f"Waiting {delay}s before next L2 request…")
                    await asyncio.sleep(delay)

                # Filter & deduplicate and write CSV
                if level2_data_for_csv:
                    unique_filtered = []
                    seen_usernames = set()
                    filtered_out = 0
                    duplicates = 0

                    logger.info(f"Filtering {len(level2_data_for_csv)} Level 2 entries…")
                    for row in level2_data_for_csv:
                        uname = row["found_l2_username"]
                        cnt = row["found_l2_count"]

                        # Only keep >= 1000 subscribers
                        if cnt < 1000:
                            filtered_out += 1
                            continue

                        if uname and uname != "N/A":
                            if uname not in seen_usernames:
                                unique_filtered.append(row)
                                seen_usernames.add(uname)
                            else:
                                duplicates += 1
                        else:
                            logger.warning(f"Skipping invalid username in L2 data: {row}")

                    logger.info(
                        f"Filtered: kept {len(unique_filtered)}, removed {filtered_out} (<1k), "
                        f"duplicates skipped: {duplicates}"
                    )

                    if unique_filtered:
                        csv_file = (saving_dir_base / f"{safe_filename_l0}_level2_report").with_suffix(".csv")
                        logger.info(f"Writing {len(unique_filtered)} to CSV: {csv_file}")
                        try:
                            with open(csv_file, "w", newline="", encoding="utf-8-sig") as csvfile:
                                fieldnames = [
                                    "Исходный канал",
                                    "Ссылка",
                                    "Кол-во подписчиков",
                                    "Название канала",
                                    "Тематика",
                                    "Каналы >50k (Ссылка)"
                                ]
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                writer.writeheader()
                                for row in unique_filtered:
                                    uname = row["found_l2_username"]
                                    title = row["found_l2_title"]
                                    cnt = row["found_l2_count"]
                                    full_url = f"https://t.me/{uname}" if uname != "N/A" else ""
                                    topic = get_channel_topic(title)
                                    over_50k_url = full_url if cnt >= 50000 else ""
                                    writer.writerow({
                                        "Исходный канал": row["source_l1"],
                                        "Ссылка": full_url,
                                        "Кол-во подписчиков": cnt,
                                        "Название канала": title,
                                        "Тематика": topic,
                                        "Каналы >50k (Ссылка)": over_50k_url
                                    })
                            logger.success(f"CSV written: {csv_file}")
                        except Exception as e:
                            logger.error(f"Failed to write CSV {csv_file}: {e}")
                    else:
                        logger.warning(f"No unique Level 2 data for CSV for {channel_username_l0}.")
                else:
                    logger.warning(f"No Level 2 data collected for {channel_username_l0}.")

                logger.success(
                    f"--- Finished Level 2 for {channel_username_l0}: "
                    f"checked {parsed_l2_count} L1 channels, found {total_l2_found} total L2 channels (before filtering) ---"
                )

        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        except Exception as e:
            logger.exception(f"Unexpected error in main loop: {e}")
        finally:
            if self.client and await self.client.is_connected():
                logger.info("Disconnecting Telegram client…")
                try:
                    await self.client.disconnect()
                    logger.info("Client disconnected.")
                except Exception as e:
                    logger.error(f"Error during disconnect: {e}")


if __name__ == "__main__":
    parser = SimilarChannelParser()
    try:
        asyncio.run(parser.main())
    except Exception as e:
        logger.critical(f"Application failed: {e}")
        if hasattr(parser, "client") and parser.client.is_connected():
            logger.warning("Attempting emergency disconnection…")
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
                if loop.is_running():
                    loop.create_task(parser.client.disconnect())
                else:
                    loop.run_until_complete(parser.client.disconnect())
                logger.info("Emergency disconnection successful.")
            except Exception as disconnect_err:
                logger.error(f"Error during emergency disconnect: {disconnect_err}")
