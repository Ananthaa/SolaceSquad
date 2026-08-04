"""Fix template to use the youtube_video_id from backend"""

# Read the file
with open('backend/templates/pages/exercises_watch.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the complex Jinja2 logic with simple variable usage
old_code = '''                    {% if video.video_url %}
                    <!-- Extract YouTube video ID from various URL formats -->
                    {% if 'youtube.com/watch?v=' in video.video_url %}
                    {% set video_id = video.video_url.split('watch?v=')[1].split('&')[0] %}
                    {% elif 'youtu.be/' in video.video_url %}
                    {% set video_id = video.video_url.split('youtu.be/')[1].split('?')[0] %}
                    {% elif 'youtube.com/embed/' in video.video_url %}
                    {% set video_id = video.video_url.split('embed/')[1].split('?')[0] %}
                    {% else %}
                    {% set video_id = video.video_url %}
                    {% endif %}
                    
                    <iframe id="video-player" class="w-full h-full"
                        src="https://www.youtube-nocookie.com/embed/{{ video_id }}?rel=0&modestbranding=1&enablejsapi=1"'''

new_code = '''                    {% if youtube_video_id %}
                    <iframe id="video-player" class="w-full h-full"
                        src="https://www.youtube-nocookie.com/embed/{{ youtube_video_id }}?rel=0&modestbranding=1&enablejsapi=1"'''

content = content.replace(old_code, new_code)

# Write back
with open('backend/templates/pages/exercises_watch.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed! Template now uses youtube_video_id from backend")
