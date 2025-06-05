import asyncio
import os
import sys
from pathlib import Path
import re # Added for parsing username
import csv # Added for CSV output

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
    "Криптовалюты/Финансы": ["крипт", "crypto", "p2p", "трейд", "инвест", "финанс", "binance", "бинанс", "trade", "invest", "finance", "nft", "нфт", "usdt", "btc", "eth"],
    "Новости/Медиа": ["новост", "news", "сми", "медиа", "media", "журнал"],
    "Технологии/IT": ["tech", "техно", "it", "айти", "разработ", "программ", "dev", "код", "code"],
    "Маркетинг/Бизнес": ["маркет", "бизнес", "business", "реклам", "пиар", "pr", "продаж", "sale"],
    "Образование": ["образ", "обучен", "курс", "урок", "школа", "school", "educat"],
    # Add more topics and keywords here
}

def get_channel_topic(title: str) -> str:
    """Determines channel topic based on keywords in the title."""
    if not title:
        return "Не определена"
    
    title_lower = title.lower() # Convert title to lowercase for case-insensitive matching
    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            # Use word boundaries (\b) to avoid partial matches (e.g., 'invest' in 'investigation')
            # Handle potential regex errors in keywords if needed
            try:
                if re.search(r'\b' + re.escape(keyword) + r'\b', title_lower):
                    return topic
            except re.error:
                # Fallback to simple substring check if regex fails for a keyword
                if keyword in title_lower:
                     return topic

    return "Не определена" # Return default if no keywords match

# --- Helper function to build regex pattern from format string ---
def build_regex_pattern(format_string: str) -> str:
    """Builds a regex pattern to parse lines based on the format string."""
    # 1. Escape the format string to treat delimiters literally
    pattern_str = re.escape(format_string)
    # 2. Replace escaped placeholders with named regex capture groups
    pattern_str = pattern_str.replace(r'\{username\}', r'(?P<username>[\w]+)')
    pattern_str = pattern_str.replace(r'\{participants_count\}', r'(?P<participants_count>\d*)')
    pattern_str = pattern_str.replace(r'\{title\}', r'(?P<title>.*)')
    # Replace any other potential generic placeholders
    pattern_str = re.sub(r'\\{.*?\\}', r'.*?', pattern_str)
    # Add anchors to match the whole line
    return f"^{pattern_str}$"

# --- Helper function to parse username from the formatted line ---
def parse_username_from_line(line: str, format_string: str) -> str | None:
    """Parses the username from a line formatted according to config.LINE_FORMAT."""
    try:
        pattern = build_regex_pattern(format_string)
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            return match.group('username')
        return None
    except re.error as e:
        logger.error(f"Regex error during username parsing line '{line}' with format '{format_string}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in parse_username_from_line for line '{line}': {e}")
        return None

# --- Helper function to parse a line into a dictionary ---
def parse_line_to_dict(line: str, format_string: str) -> dict | None:
    """Parses a line formatted according to config.LINE_FORMAT into a dictionary."""
    try:
        pattern = build_regex_pattern(format_string)
        match = re.match(pattern, line, re.IGNORECASE | re.DOTALL) # Use DOTALL in case title has newlines
        if match:
            data = {
                'username': match.group('username') or None,
                'participants_count': match.group('participants_count') or '0',
                'title': match.group('title') or 'N/A'
            }
            try:
                count_str = data['participants_count']
                data['participants_count'] = int(count_str) if count_str else 0
            except (ValueError, TypeError):
                data['participants_count'] = 0
            return data
        return None
    except re.error as e:
        logger.error(f"Regex error during dict parsing line '{line}' with format '{format_string}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in parse_line_to_dict for line '{line}': {e}")
        return None
# --- End Helper functions ---


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

    async def connect(self):
         """Connects the client if not already connected."""
         if not self.is_connected:
            logger.info("Connecting to Telegram...")
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                if not await self.client.is_user_authorized():
                     logger.info("First run or session expired: Please log in to your Telegram account.")
                     await self.client.start()
                     logger.info("Authorization successful.")
                self.is_connected = True
                logger.info("Telegram client connected successfully.")
            except Exception as e:
                 logger.error(f"Failed to connect or authorize Telegram client: {e}")
                 raise

    async def get_similar_channels(self, channel_entity: str) -> list[str]:
        """Fetches similar channels for a given channel entity."""
        if not self.is_connected:
             await self.connect()

        logger.info(f'Start parsing similar channels of "{channel_entity}"...')
        try:
            peer = channel_entity
            req = functions.channels.GetChannelRecommendationsRequest(channel=peer)
            res: types.messages.Chats = await self.client(req)
        except (ValueError, TypeError) as e:
            logger.error(f'Error fetching recommendations for "{channel_entity}": {e}. Input might be invalid, private, or not a channel.')
            return []
        except (types.errors.ChannelPrivateError, types.errors.ChatAdminRequiredError) as e:
             logger.warning(f'Cannot access recommendations for "{channel_entity}": Channel is private or requires admin rights. {e}')
             return []
        except types.errors.FloodWaitError as e:
             logger.warning(f"Flood wait error for {channel_entity}: waiting {e.seconds} seconds.")
             await asyncio.sleep(e.seconds + 1)
             return []
        except Exception as e:
             logger.error(f'An unexpected error occurred fetching recommendations for "{channel_entity}": {type(e).__name__} - {e}')
             return []

        channels: list[str] = []
        if not hasattr(res, 'chats'):
             logger.warning(f"No 'chats' attribute found in the response for {channel_entity}. Response: {res}")
             return []

        for chat in res.chats:
             if isinstance(chat, (types.Channel)) and \
                hasattr(chat, 'username') and chat.username and \
                hasattr(chat, 'participants_count') and \
                hasattr(chat, 'title'):
                 try:
                     channels.append(config.LINE_FORMAT.format(
                         username=chat.username,
                         participants_count=getattr(chat, 'participants_count', 0),
                         title=getattr(chat, 'title', 'N/A'),
                     ))
                 except KeyError as e:
                     logger.warning(f"Missing key {e} in chat object for formatting: {chat.title}. Skipping.")
                 except Exception as e:
                     logger.error(f"Error formatting chat {getattr(chat, 'title', 'N/A')}: {e}. Skipping.")
             else:
                 logger.warning(f"Skipping item because it's not a channel with required attributes: {getattr(chat, 'title', 'N/A')} (Type: {type(chat)})")

        count = getattr(res, "count", len(channels))
        log_text = f'Parsed {len(channels)}/{count if count else len(channels)} similar channels for "{channel_entity}". '
        if hasattr(res, 'count') and len(channels) < res.count:
            log_text += f"You may need Telegram Premium to get all {res.count} channels."
        logger.success(log_text)
        return channels

    async def main(self):
        """Main function to handle user input and parsing levels."""
        saving_dir_base = Path(config.SAVING_DIRECTORY)
        saving_dir_base.mkdir(exist_ok=True)

        if not saving_dir_base.is_dir():
             logger.error(
                 f"Could not create or find directory {saving_dir_base.as_posix()} to save chats in. "
                 "Please check permissions or change SAVING_DIRECTORY in config.py."
             )
             sys.exit(1)

        try:
            await self.connect()

            while True:
                channel_username_l0 = input(
                    "\nPlease input the initial channel username (e.g., @channelname or channelname, leave empty to stop): "
                ).strip()

                if not channel_username_l0:
                    logger.info("Exiting.")
                    break

                # --- Level 1 Parsing ---
                logger.info(f"--- Starting Level 1 Parsing for: {channel_username_l0} ---")
                channels_l1 = await self.get_similar_channels(channel_username_l0)

                safe_filename_l0 = channel_username_l0.lstrip('@').replace('/', '_').replace('\\', '_')
                saving_file_l1 = (saving_dir_base / f"{safe_filename_l0}_level1").with_suffix(".txt")

                if not channels_l1:
                    logger.warning(f"No similar channels found or parsed for {channel_username_l0}. Skipping Level 2.")
                    try:
                        saving_file_l1.write_text("", encoding='utf-8')
                        logger.info(f"Level 1: Empty results file created at '{saving_file_l1}'.")
                    except Exception as e:
                        logger.error(f"Failed to write empty Level 1 results file {saving_file_l1}: {e}")
                    continue

                try:
                    saving_file_l1.write_text("\n".join(channels_l1), encoding='utf-8')
                    logger.success(
                        f'Level 1: {len(channels_l1)} similar channels saved to "{saving_file_l1}" in format "{config.LINE_FORMAT}".\n'
                    )
                except Exception as e:
                     logger.error(f"Failed to save Level 1 results to {saving_file_l1}: {e}")
                     continue


                # --- Level 2 Parsing ---
                logger.info(f"--- Starting Level 2 Parsing (based on results from {channel_username_l0}) ---")

                level2_data_for_csv = []
                usernames_l1 = []
                for line in channels_l1:
                    username = parse_username_from_line(line, config.LINE_FORMAT)
                    if username:
                        usernames_l1.append(username)
                    else:
                         logger.warning(f"Could not extract username for level 2 parsing from line: '{line}'")

                if not usernames_l1:
                     logger.warning(f"No valid usernames extracted from Level 1 results of {channel_username_l0} to perform Level 2 parsing.")
                     continue

                logger.info(f"Found {len(usernames_l1)} channels from Level 1 to parse for Level 2.")

                parsed_l2_count = 0
                total_l2_channels_found = 0
                for i, channel_username_l1 in enumerate(usernames_l1, 1):
                    channel_entity_l1 = channel_username_l1 if channel_username_l1.startswith('@') else f"@{channel_username_l1}"

                    logger.info(f"--- Level 2 Parsing ({i}/{len(usernames_l1)}): Starting for {channel_entity_l1} ---")
                    channels_l2 = await self.get_similar_channels(channel_entity_l1)
                    parsed_l2_count += 1
                    total_l2_channels_found += len(channels_l2)

                    if channels_l2:
                        logger.info(f"Parsing {len(channels_l2)} L2 results from {channel_entity_l1} for CSV...")
                        for line_l2 in channels_l2:
                            parsed_data = parse_line_to_dict(line_l2, config.LINE_FORMAT)
                            if parsed_data:
                                level2_data_for_csv.append({
                                    'source_l1': channel_username_l1,
                                    'found_l2_username': parsed_data.get('username', 'N/A'),
                                    'found_l2_count': parsed_data.get('participants_count', 0),
                                    'found_l2_title': parsed_data.get('title', 'N/A')
                                })
                            else:
                                logger.warning(f"Failed to parse L2 line for CSV: '{line_l2}'")
                    else:
                         logger.info(f"Level 2: No similar channels found or parsed for {channel_entity_l1}.")

                    delay = getattr(config, 'DELAY_BETWEEN_REQUESTS', 1.5)
                    logger.debug(f"Waiting for {delay} seconds before next L2 request...")
                    await asyncio.sleep(delay)

                # --- Filter, Deduplicate Level 2 data and Write to CSV after the loop ---
                if level2_data_for_csv:
                    unique_level2_data_filtered = []
                    seen_usernames = set()
                    filtered_out_count = 0
                    duplicate_count = 0

                    logger.info(f"Filtering and deduplicating {len(level2_data_for_csv)} collected L2 results...")

                    for row_data in level2_data_for_csv:
                        l2_username = row_data.get('found_l2_username')
                        l2_count = row_data.get('found_l2_count', 0)

                        # Filter by subscriber count >= 1000
                        if l2_count < 1000:
                            filtered_out_count += 1
                            continue

                        if l2_username and l2_username != 'N/A':
                            if l2_username not in seen_usernames:
                                unique_level2_data_filtered.append(row_data)
                                seen_usernames.add(l2_username)
                            else:
                                duplicate_count += 1
                        elif not l2_username or l2_username == 'N/A':
                             logger.warning(f"Skipping row during deduplication due to invalid username: {row_data}")

                    logger.info(f"Filtering complete: Kept {len(unique_level2_data_filtered)} channels (>1k subs, unique). "
                                f"Filtered out {filtered_out_count} (<1k subs). Found {duplicate_count} duplicates (>1k subs).")

                    if unique_level2_data_filtered:
                        csv_filename = (saving_dir_base / f"{safe_filename_l0}_level2_report").with_suffix(".csv")
                        logger.info(f"Writing {len(unique_level2_data_filtered)} unique & filtered Level 2 results to CSV: {csv_filename}")
                        try:
                            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                                # *** CHANGED: Added 'Тематика' fieldname ***
                                fieldnames = ['Исходный канал', 'Ссылка', 'Кол-во подписчиков', 'Название канала', 'Тематика', 'Каналы >50k (Ссылка)']
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                                writer.writeheader()
                                for row_data in unique_level2_data_filtered:
                                    l2_username = row_data['found_l2_username']
                                    l2_title = row_data['found_l2_title']
                                    l2_count = row_data['found_l2_count']

                                    full_url = f"https://t.me/{l2_username}" if l2_username and l2_username != 'N/A' else ''

                                    # *** ADDED: Determine topic ***
                                    topic = get_channel_topic(l2_title)

                                    channel_over_50k_url = ''
                                    if l2_count >= 50000:
                                        channel_over_50k_url = full_url

                                    writer.writerow({
                                        'Исходный канал': row_data['source_l1'],
                                        'Ссылка': full_url,
                                        'Кол-во подписчиков': l2_count,
                                        'Название канала': l2_title,
                                        'Тематика': topic, # Write the determined topic
                                        'Каналы >50k (Ссылка)': channel_over_50k_url
                                    })
                            logger.success(f"Successfully wrote unique & filtered Level 2 results to {csv_filename}")
                        except IOError as e:
                            logger.error(f"Failed to write CSV file {csv_filename}: {e}")
                        except Exception as e:
                            logger.error(f"An unexpected error occurred while writing CSV {csv_filename}: {e}")
                    else:
                         logger.warning(f"No unique Level 2 data remaining after filtering (>1k subs) for {channel_username_l0}.")

                else:
                    logger.warning(f"No Level 2 data collected to write to CSV for {channel_username_l0}.")


                logger.success(f"--- Finished Level 2 Parsing for channels related to {channel_username_l0}. Attempted {parsed_l2_count} L1 channels, found {total_l2_channels_found} L2 channels in total (before filtering & deduplication). ---")

        except KeyboardInterrupt:
             logger.info("Process interrupted by user.")
        except Exception as e:
             logger.exception(f"An unexpected error occurred in the main loop: {e}")
        finally:
            if self.client and self.client.is_connected():
                logger.info("Disconnecting Telegram client...")
                try:
                    await self.client.disconnect()
                    logger.info("Telegram client disconnected.")
                except Exception as e:
                    logger.error(f"Error during client disconnection: {e}")


if __name__ == "__main__":
    parser = SimilarChannelParser()
    try:
        asyncio.run(parser.main())
    except Exception as e:
         logger.critical(f"Application failed to run: {e}")
         if hasattr(parser, 'client') and parser.client.is_connected:
             logger.warning("Attempting emergency client disconnection...")
             try:
                 loop = asyncio.get_event_loop_policy().get_event_loop()
                 if loop.is_running():
                      loop.create_task(parser.client.disconnect())
                 else:
                      loop.run_until_complete(parser.client.disconnect())
                 logger.info("Emergency disconnection successful.")
             except Exception as disconnect_err:
                 logger.error(f"Error during emergency disconnection: {disconnect_err}")

