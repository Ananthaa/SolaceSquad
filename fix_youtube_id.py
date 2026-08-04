"""Add YouTube video ID extraction to the watch video route"""

# Read the file
with open('backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "return templates.TemplateResponse(" around line 4701
for i, line in enumerate(lines):
    if i >= 4698 and i <= 4705 and 'return templates.TemplateResponse(' in line and 'exercises_watch.html' in lines[i+1]:
        # Insert YouTube ID extraction before this line
        indent = '        '
        extraction_code = [
            f'{indent}# Extract YouTube video ID from URL\n',
            f'{indent}youtube_video_id = None\n',
            f'{indent}if video.video_url:\n',
            f'{indent}    url = video.video_url\n',
            f'{indent}    if "youtube.com/watch?v=" in url:\n',
            f'{indent}        youtube_video_id = url.split("watch?v=")[1].split("&")[0]\n',
            f'{indent}    elif "youtu.be/" in url:\n',
            f'{indent}        youtube_video_id = url.split("youtu.be/")[1].split("?")[0]\n',
            f'{indent}    elif "youtube.com/embed/" in url:\n',
            f'{indent}        youtube_video_id = url.split("embed/")[1].split("?")[0]\n',
            f'{indent}    else:\n',
            f'{indent}        # Assume it\'s just the video ID\n',
            f'{indent}        youtube_video_id = url\n',
            f'{indent}\n',
        ]
        
        # Insert the code
        for j, code_line in enumerate(extraction_code):
            lines.insert(i + j, code_line)
        
        # Now find the template response dict and add youtube_video_id
        # Look for the closing brace of the dict
        for k in range(i + len(extraction_code), i + len(extraction_code) + 20):
            if '"related_videos": related_videos' in lines[k]:
                # Add youtube_video_id after related_videos
                lines[k] = lines[k].rstrip() + ',\n'
                lines.insert(k + 1, f'{indent}        "youtube_video_id": youtube_video_id\n')
                break
        
        break

# Write back
with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed! Added YouTube video ID extraction to the watch video route")
