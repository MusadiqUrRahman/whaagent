# YouTube Transcript Tool

Extract and analyze transcripts from YouTube videos.

## YouTubeTranscriptTool

```python
from whaagent.tools import YouTubeTranscriptTool

tool = YouTubeTranscriptTool()
transcript = tool.invoke("dQw4w9WgXcQ")
```

### Properties
- **name**: `youtube_transcript`
- **description**: Extract transcript from a YouTube video

### Input
- YouTube video ID (e.g., `dQw4w9WgXcQ`)
- Or full YouTube URL

### Output
Transcript text with timestamps.

## Features

### Automatic Caching
Transcripts are cached locally for faster repeated access:
- **Location**: `~/.whaagent/youtube_cache/`
- **Format**: JSON with metadata
- **Expiration**: 30 days

### Multiple Languages
Attempts to get English transcript first, falls back to available languages.

### Timestamp Support
Returns timestamps for reference:

```
[0:00] Welcome to this video
[0:15] Today we're going to talk about...
[0:30] Let's start with the basics
```

## Usage Examples

### Basic Usage

```python
from whaagent.tools import YouTubeTranscriptTool

tool = YouTubeTranscriptTool()

# With video ID
transcript = tool.invoke("dQw4w9WgXcQ")

# With URL
transcript = tool.invoke("https://youtube.com/watch?v=dQw4w9WgXcQ")
```

### In an Agent

```python
from typing import Sequence, Any
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry
from whaagent.tools import YouTubeTranscriptTool

@AgentRegistry.register("video-analyst")
class VideoAnalystAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You analyze YouTube videos based on their transcripts."

    def local_tools(self) -> Sequence[Any]:
        tool = YouTubeTranscriptTool()
        return [
            StructuredTool.from_function(
                func=tool.invoke,
                name=tool.name,
                description=tool.description,
            )
        ]
```

### CLI Usage

```bash
whaagent youtube -i "Summarize video dQw4w9WgXcQ"
whaagent youtube -i "What are the main points in https://youtube.com/watch?v=abc123"
```

## Cache Management

### View Cache

```python
from whaagent.tools.youtube_cache import YouTubeCache

cache = YouTubeCache()
entries = cache.list_entries()
for entry in entries:
    print(f"{entry.video_id}: {entry.title}")
```

### Clear Cache

```bash
rm -rf ~/.whaagent/youtube_cache/
```

### Custom Cache Location

```python
from whaagent.tools.youtube_cache import YouTubeCache

cache = YouTubeCache(cache_dir="/custom/path")
```

## Error Handling

The tool returns descriptive error messages:

```python
# Invalid video ID
tool.invoke("invalid")
# Returns: "Error: Could not extract video ID from input"

# Video unavailable
tool.invoke("nonexistent123")
# Returns: "Error: Transcript not available for this video"
```

## Limitations

- Requires video to have captions/transcripts
- Some videos may not have transcripts available
- Auto-generated transcripts may have accuracy issues
- Rate limiting may occur with many requests

## See Also

- [Tools Overview](index.md) - All available tools
- [Built-in Agents](../agents/built-in.md#youtube) - YouTube agent
