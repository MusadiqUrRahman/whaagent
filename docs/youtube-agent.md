# YouTube Agent

The YouTube agent specializes in extracting and analyzing content from YouTube videos.

## Capabilities

- **Video Summarization**: Get concise summaries without watching
- **Q&A**: Ask questions about specific topics in videos
- **Key Points**: Extract main ideas with timestamps
- **Multi-language**: Automatic language detection and translation
- **Local Caching**: Transcripts are cached locally for faster repeated access

## Usage

### Basic Summarization

```bash
bin/whaagent.sh youtube -i "Summarize https://www.youtube.com/watch?v=VIDEO_ID"
```

### Specific Questions

```bash
bin/whaagent.sh youtube -i "What does this video say about machine learning? https://..."
```

### Extract Key Points

```bash
bin/whaagent.sh youtube -i "Extract the top 5 key points from this video with timestamps: https://..."
```

### Video Analysis

```bash
bin/whaagent.sh youtube -i "Analyze the arguments presented in this video: https://..."
```

## Limitations

- Videos must have captions (auto-generated or manual)
- Private or region-restricted videos cannot be accessed
- Live streams require completed processing for transcripts
- Video quality depends on caption accuracy

## Error Handling

The agent provides clear messages when:
- Video URL is invalid
- Captions are disabled
- Video is unavailable/private
- No supported language transcripts exist

## Cache

The agent uses local SQLite caching to store transcripts and avoid repeated API calls. Cache location: `storage/youtube/transcripts.db`.

- Default cache size: 100MB
- Default TTL: 30 days
- LRU eviction when cache exceeds size limit

## Examples

### Example 1: Summarize a technical talk

```bash
bin/whaagent.sh youtube -i "Summarize the key points of this video in bullet points: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Example 2: Ask about specific topic

```bash
bin/whaagent.sh youtube -i "What does the speaker say about the future of AI? https://www.youtube.com/watch?v=..."
```

### Example 3: Compare multiple videos

```bash
bin/whaagent.sh youtube -i "Compare the approaches presented in these two videos: https://... and https://..."
```
