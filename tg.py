import os
import asyncio
import subprocess
import requests
from telethon.sync import TelegramClient
from telethon.tl.types import Channel, DocumentAttributeVideo
import shutil

# ========== CONFIG ==========
phone_number = '+91 7026046541'
api_id = 26894200
api_hash = '834cfa6ec2b0a1931a27d52d28d8838e'

SOURCE_CHANNEL_USERNAME = 'ourcommunityforbd'
DESTINATION_CHANNEL_USERNAME = 'shcommunityforbd'

BOT_TOKEN = '7525682158:AAGZBfP-OzPvZMsHZgG0o_B7t3H-3P3UtA'
TARGET_USER_ID = '7598595878'

DOWNLOAD_DIR = 'temp_telegram_media'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
# ============================


# -------- Simple ffmpeg check --------
def check_ffmpeg():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        print("✅ FFmpeg is installed and ready.")
        return True
    else:
        print("⚠ FFmpeg is NOT installed or not found in PATH. Please ensure ffmpeg is installed.")
        return False


# -------- Bot Message --------
def send_bot_message(text: str):
    """Send a message to the user via bot."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TARGET_USER_ID, "text": text}
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print("  ✅ Sent link to user via bot.")
        else:
            print(f"  ❌ Failed to send link via bot: {r.text}")
    except Exception as e:
        print(f"  ❌ Error sending bot message: {e}")


# -------- Audio Check --------
def has_audio(file_path):
    """Check if the video has an audio stream using ffprobe."""
    cmd = [
        "ffprobe", "-i", file_path, "-show_streams",
        "-select_streams", "a", "-loglevel", "error"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return bool(result.stdout.strip())


# -------- Add Silent Audio --------
def add_silent_audio(input_path, output_path):
    """Add a silent audio track to the video."""
    cmd = [
        "ffmpeg", "-i", input_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        output_path, "-y"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# -------- Main Function --------
async def copy_posts_in_range(start_number: int, end_number: int):
    """Copy posts from start_number to end_number from source to destination."""
    session_name = f"session_{phone_number.replace('+', '').replace(' ', '')}"
    client = TelegramClient(session_name, api_id, api_hash)

    try:
        print("Connecting to Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("Not authorized. Logging in...")
            await client.start(phone=phone_number)
            print("Successfully logged in.")
        else:
            print("Already authorized.")

        source_channel = await client.get_entity(SOURCE_CHANNEL_USERNAME)
        destination_channel = await client.get_entity(DESTINATION_CHANNEL_USERNAME)

        print(f"Copying posts #{start_number} to #{end_number}...")

        count = 0
        async for message in client.iter_messages(
            source_channel,
            min_id=start_number - 1,
            max_id=end_number + 1,
            reverse=True
        ):
            if message.id < start_number or message.id > end_number:
                continue

            print(f"Processing post #{message.id}...")
            post_url = f"https://t.me/{source_channel.username}/{message.id}"
            sent_success = False

            if message.text and not message.media:
                await client.send_message(destination_channel, message.text)
                print("  Sent text.")
                sent_success = True

            elif message.media:
                file_path = None
                try:
                    file_path = await message.download_media(file=DOWNLOAD_DIR)
                    if file_path:
                        if message.photo:
                            await client.send_file(
                                destination_channel,
                                file_path,
                                caption=message.text or ""
                            )
                            print("  Sent photo.")
                            sent_success = True

                        elif message.video or file_path.lower().endswith(".mp4"):
                            fixed_path = file_path
                            if not has_audio(file_path):
                                fixed_path = os.path.join(DOWNLOAD_DIR, "fixed_" + os.path.basename(file_path))
                                add_silent_audio(file_path, fixed_path)
                                print("  Added silent audio track.")

                            video_attrs = DocumentAttributeVideo(
                                duration=1,
                                w=720,
                                h=1280,
                                supports_streaming=True
                            )
                            await client.send_file(
                                destination_channel,
                                fixed_path,
                                caption=message.text or "",
                                supports_streaming=True,
                                mime_type="video/mp4",
                                attributes=[video_attrs]
                            )
                            print("  Sent as real video.")
                            sent_success = True

                        else:
                            print("  Unsupported media type, skipped.")

                finally:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                    if 'fixed_path' in locals() and fixed_path != file_path and os.path.exists(fixed_path):
                        os.remove(fixed_path)

            if sent_success:
                send_bot_message(f"✅ New post copied: {post_url}")
                count += 1

        print(f"✅ Finished copying {count} posts from #{start_number} to #{end_number}.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()


if __name__ == '__main__':
    if check_ffmpeg():
        start_number = int(input("Enter the starting post number: ").replace("/", ""))
        end_number = int(input("Enter the ending post number: ").replace("/", ""))
        asyncio.run(copy_posts_in_range(start_number, end_number))
    else:
        print("Please install ffmpeg and try again.")
