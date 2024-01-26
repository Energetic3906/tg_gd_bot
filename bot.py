import os
import logging
import subprocess
import yt_dlp
import requests
from urllib.parse import urlparse
from pyrogram import Client, filters, types, enums

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
authorized_users_env = os.environ.get("AUTHORIZED_USERS")

# 将环境变量值解析为实际的用户ID列表
AUTHORIZED_USERS = [int(user_id) for user_id in authorized_users_env.split(",")] if authorized_users_env else []
# 定义Pyrogram客户端
app = Client('/app/bot/my_bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 配置日志记录器
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def private_use(func):
    def wrapper(client: Client, message: types.Message):
        chat_id = getattr(message.from_user, "id", None)

        if chat_id not in AUTHORIZED_USERS:
            client.send_message(chat_id, "You are not authorized to use this bot.")
            return

        # message type check
        if message.chat.type != enums.ChatType.PRIVATE and not message.text.lower().startswith("/ytdl"):
            logging.debug("%s, it's annoying me...🙄️ ", message.text)
            return

        return func(client, message)

    return wrapper

@app.on_message(filters.command(["start"]))
@private_use
def start_command(client, message):
    message.reply_text("The bot is running.")

@app.on_message(filters.text & filters.private)
@private_use
def handle_text_message(client, message):
    video_link = message.text.strip()
    domain = urlparse(video_link).hostname

    if domain in ('www.youtube.com', 'youtu.be', 'youtube.com'):
        paths = '/app/google_drive/youtube'
        cookies = None
    elif domain in ('www.bilibili.com', 'b23.tv'):
        paths = '/app/google_drive/bilibili'
        cookies = '/app/bilibili_cookie/cookies.txt'
    else:
        message.reply_text("Invalid video link. Please provide a link from YouTube or Bilibili.")
        return

    ydl = yt_dlp.YoutubeDL()
    info = ydl.extract_info(video_link, download=False)
    
    # 从视频信息中获取标题和缩略图 URL
    filename = info.get("title")

    thumbnail_url = info.get("thumbnail")
        
    # 使用 requests 下载缩略图
    response = requests.get(thumbnail_url)

    thumbnail_filename = os.path.join(paths, f"{filename}.jpg")

    with open(thumbnail_filename, 'wb') as f:
        f.write(response.content)


    command = [
        'yt-dlp',
        '-f', 'bestvideo+bestaudio/best',
        video_link,
        '--paths', paths,
        '--output', filename,
        '--write-subs',
        '--write-auto-subs',
        '--sub-langs', 'zh.*',
        '--merge-output-format', 'mkv',
        '--external-downloader', 'aria2c',
        '--external-downloader-args', '-x 5 -k 4M'
    ]

    if cookies:
        command.extend(['--cookies', cookies])

    # 发送 "Downloading in progress." 消息
    downloading_message = message.reply_text("Downloading in progress.", reply_to_message_id=message.id)

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while True:
        output = process.stdout.readline().decode().strip()
        if output == '' and process.poll() is not None:
            break

        logger.info(output)

        if "ERROR" in output:
            downloading_message.delete()
            message.reply_text("An error occurred during video download.", reply_to_message_id=message.id)
            break
        elif "has already been downloaded" in output:
            downloading_message.delete()
            message.reply_text("Video has already been downloaded.", reply_to_message_id=message.id)
            break
        elif "Deleting original file" in output:
            downloading_message.delete()
            message.reply_text("Video download complete.", reply_to_message_id=message.id)
            break
        elif "are missing" in output:
            downloading_message.delete()
            message.reply_text("Bilibili cookies expired, please update.", reply_to_message_id=message.id)
            process.terminate()  # 停止下载进程
            break

if __name__ == '__main__':
    app.run()
