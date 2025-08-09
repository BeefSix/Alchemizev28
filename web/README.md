# Alchemize Web Frontend

A modern Next.js 14 frontend for the Alchemize AI video processing platform, featuring real-time video upload, processing, and clip generation with live karaoke captions.

## 🚀 Features

- **Modern UI/UX**: Built with Next.js 14 App Router and Tailwind CSS
- **Real-time Processing**: Server-Sent Events (SSE) for live job progress updates
- **Chunked File Upload**: Efficient large file uploads with progress tracking
- **JWT Authentication**: Secure authentication with httpOnly cookies
- **Responsive Design**: Mobile-first design that works on all devices
- **Video Preview**: Built-in video player for generated clips
- **Job History**: Track and manage all your video processing jobs

## 🛠️ Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **UI Components**: Custom component library with shadcn/ui patterns
- **Icons**: Lucide React
- **Notifications**: React Hot Toast
- **File Upload**: React Dropzone
- **Animations**: Framer Motion

## 📦 Installation

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Set up environment variables**:
   Create a `.env.local` file in the root directory:
   ```env
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```

4. **Open your browser**:
   Navigate to [http://localhost:3000](http://localhost:3000)

## 🏗️ Project Structure

```
web/
├── app/                    # Next.js App Router pages
│   ├── globals.css        # Global styles
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page
│   ├── login/             # Authentication pages
│   └── register/
├── components/            # React components
│   ├── ui/               # Reusable UI components
│   ├── video-upload.tsx  # Video upload component
│   └── job-progress.tsx  # Job progress component
├── lib/                  # Utility functions
│   ├── api.ts           # API client
│   └── utils.ts         # Helper functions
├── store/               # Zustand stores
│   ├── auth.ts         # Authentication state
│   └── jobs.ts         # Job management state
├── types/               # TypeScript type definitions
└── public/              # Static assets
```

## 🔧 Configuration

### API Configuration

The frontend connects to your FastAPI backend. Make sure your backend is running on `http://localhost:8000` or update the `NEXT_PUBLIC_API_BASE_URL` environment variable.

### CORS Configuration

Your FastAPI backend should allow CORS from `http://localhost:3000`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🎯 Key Components

### VideoUpload Component

Handles file selection, validation, and upload with:
- Drag & drop interface
- File type validation
- Progress tracking
- Processing options (captions, aspect ratio, platforms)

### JobProgress Component

Displays real-time job status with:
- Progress bars and status indicators
- SSE connection for live updates
- Video preview for completed clips
- Download functionality

### Authentication

JWT-based authentication with:
- Login/Register pages
- Persistent sessions
- Protected routes
- Automatic token refresh

## 🔄 Real-time Updates

The frontend uses Server-Sent Events (SSE) to receive real-time updates from the backend:

```typescript
// Subscribe to job events
const unsubscribe = apiClient.subscribeToJobEvents(jobId, (event) => {
  // Handle real-time updates
  console.log('Job status:', event.status);
  console.log('Progress:', event.percent);
});
```

## 📱 Responsive Design

The interface is fully responsive and optimized for:
- Desktop (1024px+)
- Tablet (768px - 1023px)
- Mobile (320px - 767px)

## 🎨 Customization

### Colors

The color scheme can be customized in `tailwind.config.js`:

```javascript
theme: {
  extend: {
    colors: {
      primary: {
        50: '#f0f9ff',
        500: '#0ea5e9',
        600: '#0284c7',
        // ... more shades
      },
      // ... other color palettes
    }
  }
}
```

### Components

UI components are built using a variant system for easy customization:

```typescript
<Button variant="primary" size="lg">
  Custom Button
</Button>
```

## 🚀 Deployment

### Vercel (Recommended)

1. Push your code to GitHub
2. Connect your repository to Vercel
3. Set environment variables in Vercel dashboard
4. Deploy automatically on push

### Other Platforms

The app can be deployed to any platform that supports Next.js:

```bash
# Build for production
npm run build

# Start production server
npm start
```

## 🔒 Security Features

- JWT tokens stored in httpOnly cookies
- CORS protection
- Input validation and sanitization
- Secure file upload handling
- Rate limiting support

## 📊 Performance

- Code splitting with Next.js
- Optimized images with Next.js Image component
- Efficient state management with Zustand
- Lazy loading for components
- Optimized bundle size

## 🧪 Testing

```bash
# Run type checking
npm run type-check

# Run linting
npm run lint

# Run tests (when implemented)
npm test
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is part of the Alchemize platform. See the main project license for details.

## 🆘 Support

For support and questions:
- Check the main project documentation
- Open an issue on GitHub
- Contact the development team

## 🔗 Related Links

- [Backend API Documentation](../README.md)
- [FastAPI Backend](../app/)
- [Deployment Guide](../PRODUCTION_GUIDE.md)
