"""Fix the youtube_url to video_url in exercises_watch.html"""

# Read the file
with open('backend/templates/pages/exercises_watch.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace youtube_url with video_url
content = content.replace('video.youtube_url', 'video.video_url')

# Write back
with open('backend/templates/pages/exercises_watch.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed! Replaced 'video.youtube_url' with 'video.video_url'")
