import os
import random
import librosa
from dotenv import load_dotenv
import discord
from discord.ext import commands
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from moviepy.video.fx.all import lum_contrast
import concurrent.futures
import asyncio

# Load environment variables from .env file
load_dotenv()

# Define intents
intents = discord.Intents.default()
intents.message_content = True

# Create an instance of a bot with intents
bot = commands.Bot(command_prefix='!', intents=intents)

def process_video(video_files, audio_path, total_duration, output_path):
    # Load the audio file and detect beats
    y, sr = librosa.load(audio_path)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # Shuffle the video files to ensure random order
    random.shuffle(video_files)

    # Load video clips and synchronize with beats
    clips = []
    current_duration = 0
    video_index = 0
    beat_index = 0

    while current_duration < total_duration and beat_index < len(beat_times) - 1:
        video = video_files[video_index % len(video_files)]
        clip = VideoFileClip(os.path.join('Video', video))
        
        # Determine clip duration based on beats
        clip_duration = min(beat_times[beat_index + 1] - beat_times[beat_index], total_duration - current_duration)
        
        if clip_duration <= 0:
            break
        
        # Apply a stronger low exposure filter
        clip = clip.subclip(0, clip_duration).fx(lum_contrast, lum=-0.5, contrast=0.3)
        clips.append(clip)
        current_duration += clip_duration
        
        video_index += 1
        beat_index += 1

    # Check if clips list is empty
    if not clips:
        return

    # Concatenate video clips
    final_video = concatenate_videoclips(clips, method="compose")

    # Load and set the audio
    audio_clip = AudioFileClip(audio_path)
    final_video = final_video.set_audio(audio_clip)

    # Ensure the final video duration matches the total duration
    final_video = final_video.subclip(0, total_duration)

    # Export the final video
    final_video.write_videofile(output_path, codec='libx264', audio_codec='aac', remove_temp=True, threads=4)

@bot.command(name='generate')
async def list_songs(ctx):
    audio_dir = 'Audio'
    audio_files = [f for f in os.listdir(audio_dir) if f.endswith('.mp3')]

    if not audio_files:
        await ctx.send("No audio files found in the Audio directory.")
        return

    # List available songs
    song_list = "\n".join([f"{i+1}. {audio_files[i]}" for i in range(len(audio_files))])
    await ctx.send(f"Available songs:\n{song_list}\n\nPlease respond with the number of the song you want to select.")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        song_index = int(msg.content) - 1

        if 0 <= song_index < len(audio_files):
            selected_audio = audio_files[song_index]
            await ctx.send(f"You selected: {selected_audio}")
            await create_video(ctx, selected_audio)
        else:
            await ctx.send("Invalid selection. Please try again.")
    except asyncio.TimeoutError:
        await ctx.send("You took too long to respond. Please try again.")

async def create_video(ctx, selected_audio):
    video_dir = 'Video'
    audio_dir = 'Audio'
    audio_path = os.path.join(audio_dir, selected_audio)

    # Output path for the final video
    output_path = 'output_video.mp4'

    # Start video processing in a separate thread
    with concurrent.futures.ThreadPoolExecutor() as executor:
        await ctx.send("Starting video creation...")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, process_video, os.listdir(video_dir), audio_path, 15, output_path)

    # Send the video file to the channel
    await ctx.send(file=discord.File(output_path))
    await ctx.send("Video creation complete!")

# Run the bot with your token
bot.run(os.getenv('DISCORD_BOT_TOKEN'))