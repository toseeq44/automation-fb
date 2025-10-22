# 🔗 Enhanced Link Grabber - Advanced Video Link Extraction

## Overview
The Enhanced Link Grabber is a powerful tool that can extract video links from public creators' pages on YouTube, Instagram, TikTok, and Facebook by inspecting page source code and using multiple extraction methods.

## ✨ New Features

### 🔍 Page Inspection Technology
- **Direct HTML Parsing**: Inspects page source code to find video links
- **Multiple Extraction Methods**: Uses 4+ different techniques per platform
- **JSON Data Mining**: Extracts video data from embedded JSON structures
- **Smart Link Detection**: Finds video links in various formats and attributes

### 📋 Bulk Processing
- **Multiple URL Support**: Process multiple URLs at once
- **Batch Extraction**: Extract from multiple creators simultaneously
- **Progress Tracking**: Real-time progress for bulk operations
- **Error Handling**: Continues processing even if some URLs fail

### 🎯 Platform-Specific Enhancements

#### YouTube
- **Channel Page Inspection**: Extracts all videos from channel pages
- **Playlist Support**: Handles YouTube playlists
- **Video ID Detection**: Finds video IDs in data attributes
- **ytInitialData Mining**: Extracts from YouTube's complex data structure

#### Instagram
- **Profile Page Scanning**: Finds all posts and reels from profiles
- **Reel Detection**: Specifically targets Instagram Reels
- **Post Link Extraction**: Finds /p/ and /reel/ links
- **JSON Data Parsing**: Extracts from window._sharedData

#### TikTok
- **User Profile Scanning**: Extracts videos from TikTok profiles
- **Video Link Detection**: Finds /video/ and @username/video/ links
- **SIGI_STATE Mining**: Extracts from TikTok's data structure
- **Author-Video Mapping**: Constructs proper TikTok URLs

#### Facebook
- **Page Video Extraction**: Finds videos from Facebook pages
- **Multiple Link Formats**: Handles /videos/, /watch/, and fb.watch links
- **Video ID Detection**: Finds video IDs in data attributes
- **Profile Video Scanning**: Extracts from public profiles

## 🚀 How to Use

### Single URL Extraction
1. Open the Link Grabber module
2. Paste a single URL (channel, profile, playlist, etc.)
3. Choose extraction mode:
   - **Extract ALL videos**: Gets all available videos
   - **Extract specific number**: Limits to a specific count
4. Click "🚀 Start Extraction"
5. Watch the circular progress bar and real-time results

### Bulk URL Extraction
1. Check "📋 Bulk Mode (Multiple URLs)"
2. Paste multiple URLs (one per line):
   ```
   https://www.youtube.com/@MrBeast
   https://www.instagram.com/cristiano/
   https://www.tiktok.com/@charlidamelio
   https://www.facebook.com/NASA
   ```
3. Choose extraction mode
4. Click "🚀 Start Extraction"
5. Monitor bulk progress across all URLs

## 🔧 Technical Details

### Extraction Methods
Each platform uses multiple extraction techniques:

1. **API-Based Extraction** (Primary)
   - YouTube Data API v3
   - Instagram Instaloader
   - yt-dlp for all platforms

2. **Page Inspection** (Secondary)
   - HTML parsing with BeautifulSoup
   - JSON data extraction
   - Link pattern matching
   - Data attribute mining

3. **Fallback Methods** (Tertiary)
   - yt-dlp generic extraction
   - Direct URL processing

### Supported URL Formats

#### YouTube
- `https://www.youtube.com/@username`
- `https://www.youtube.com/channel/UC...`
- `https://www.youtube.com/c/username`
- `https://www.youtube.com/playlist?list=...`

#### Instagram
- `https://www.instagram.com/username/`
- `https://www.instagram.com/p/shortcode/`
- `https://www.instagram.com/reel/shortcode/`

#### TikTok
- `https://www.tiktok.com/@username`
- `https://www.tiktok.com/video/1234567890`
- `https://www.tiktok.com/@username/video/1234567890`

#### Facebook
- `https://www.facebook.com/username`
- `https://www.facebook.com/username/videos`
- `https://fb.watch/...`

## 📊 Features

### Real-time Progress
- Circular progress bar with smooth animation
- Live status updates
- Link counter
- Platform detection

### Export Options
- **Export to TXT**: Save all links to a text file
- **Copy to Clipboard**: Copy all URLs for pasting
- **Clear Results**: Reset for new extraction

### Error Handling
- Graceful fallbacks between extraction methods
- Detailed error messages
- Continues processing on individual failures
- Cancellation support

## 🛠️ Installation

### Dependencies
```bash
pip install -r requirements.txt
```

### Required Packages
- `yt-dlp>=2024.3.10`
- `PyQt5>=5.15.9`
- `requests>=2.31.0`
- `google-api-python-client>=2.0.0`
- `instaloader>=4.9.0`
- `beautifulsoup4>=4.12.0`
- `lxml>=4.9.0`

## 🎯 Use Cases

### Content Creators
- Monitor competitor channels
- Track trending videos
- Analyze content strategies
- Find inspiration sources

### Researchers
- Study social media trends
- Analyze video content patterns
- Track viral content
- Monitor platform activity

### Marketers
- Find relevant content for campaigns
- Track brand mentions
- Monitor influencer activity
- Analyze engagement patterns

## ⚠️ Important Notes

### Legal Considerations
- Only extracts from **public** profiles and pages
- Respects platform terms of service
- No private content access
- Rate limiting to prevent server overload

### Technical Limitations
- Some platforms may block automated access
- Private accounts cannot be accessed
- Rate limits may apply
- Some content may require login

### Best Practices
- Use reasonable delays between requests
- Don't overwhelm servers with too many requests
- Respect robots.txt and terms of service
- Use for legitimate research purposes only

## 🔄 Updates and Improvements

### Recent Enhancements
- ✅ Added page inspection capabilities
- ✅ Implemented bulk URL processing
- ✅ Enhanced error handling and fallbacks
- ✅ Improved UI with circular progress
- ✅ Added platform-specific optimizations

### Future Plans
- 🔄 Add more social media platforms
- 🔄 Implement video metadata extraction
- 🔄 Add scheduling and automation
- 🔄 Create API endpoints
- 🔄 Add video thumbnail extraction

## 🆘 Troubleshooting

### Common Issues
1. **"Page inspection failed"**: Try the yt-dlp fallback
2. **"No links found"**: Check if the profile/page is public
3. **"Rate limited"**: Wait a few minutes and try again
4. **"Invalid URL"**: Ensure URL format is correct

### Getting Help
- Check the error messages for specific details
- Try different extraction methods
- Verify the URL is accessible
- Check your internet connection

## 📈 Performance Tips

### For Best Results
- Use single URL mode for detailed extraction
- Use bulk mode for quick overview
- Set reasonable limits (50-100 videos max)
- Process during off-peak hours
- Monitor progress and cancel if needed

### Optimization
- Close other applications during bulk processing
- Use wired internet connection
- Ensure sufficient RAM (4GB+ recommended)
- Process in smaller batches for large operations

---

**🎉 Enjoy extracting video links with the Enhanced Link Grabber!**

*Remember to use this tool responsibly and in accordance with platform terms of service.*
