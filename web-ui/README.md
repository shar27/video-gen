# 🎬 Islamophobia UK - Video Commentary Web UI

Beautiful web interface for the automated video commentary pipeline.

## 📸 Features

- ✅ Submit videos by YouTube URL or Incident ID
- ✅ Real-time processing status
- ✅ Auto-generated YouTube metadata (title, description, tags)
- ✅ One-click copy for YouTube upload
- ✅ Download final processed videos
- ✅ Responsive design (mobile-friendly)
- ✅ Professional gradient UI

## 🚀 Quick Start

### Development

```bash
cd web-ui
npm install
npm run dev
```

Visit: http://localhost:5173

### Production Build

```bash
npm run build
```

Output in `dist/` folder.

### Deploy to Netlify

```bash
npm install -g netlify-cli
netlify login
netlify init
netlify deploy --prod
```

## 🔧 Configuration

Create `.env` file:

```
VITE_API_URL=https://your-backend-api.com
```

## 📦 Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool (super fast!)
- **Axios** - HTTP client
- **CSS3** - Gradient styling

## 🎨 Screenshots

[Your UI will show]
- Video submission form
- Processing status
- YouTube metadata display
- Download button

## 📄 License

Educational use for Islamophobia UK

## 🔗 Links

- Website: https://islamophobiauk.co.uk
- YouTube: @IslamophobiaUK
