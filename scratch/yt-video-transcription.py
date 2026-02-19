import os

import yt_dlp
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])


def transcribe_youtube(url):
    # 1. configure yt-dlp to extract audio only
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'temp_audio.%(ext)s',  # temporary filename
    }

    # 2. download the audio
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # 3. transcribe with whisper API
    audio_file = open("temp_audio.mp3", "rb")
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

    # 4. cleanup
    audio_file.close()
    os.remove("temp_audio.mp3")

    return transcription.text


video_url = "https://www.youtube.com/shorts/psoFK7p1x4s"
print(transcribe_youtube(video_url))
