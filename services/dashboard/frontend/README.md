# Email Management Dashboard - Frontend

React + TypeScript + Vite frontend for the Email Management Dashboard.

## Features

- **Authentication**: Secure login with session management
- **Dashboard Home**: Overview of email processing statistics
- **Approval Queue**: Review and approve low-confidence email classifications
- **Inbox Monitor**: Real-time view of inbox with filtering
- **Statistics**: Charts and metrics for processing accuracy
- **Settings**: Whitelist management for protected companies

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Styling
- **React Router** - Routing
- **React Query** - Data fetching and caching
- **Axios** - HTTP client
- **Recharts** - Data visualization
- **date-fns** - Date formatting

## Project Structure

```
src/
├── api/
│   └── client.ts           # API client wrapper
├── components/
│   └── Layout.tsx          # Main layout with navigation
├── contexts/
│   └── AuthContext.tsx     # Authentication context
├── hooks/
│   └── useAuth.ts          # Auth hook
├── pages/
│   ├── LoginPage.tsx       # Login page
│   ├── DashboardPage.tsx   # Dashboard home
│   ├── ApprovalsPage.tsx   # Approval queue
│   ├── InboxPage.tsx       # Inbox monitor
│   ├── StatsPage.tsx       # Statistics
│   └── SettingsPage.tsx    # Settings & whitelist
├── types/
│   └── index.ts            # TypeScript types
├── App.tsx                 # Main app component
├── main.tsx                # Entry point
└── index.css               # Global styles
```

## Quick Start

### 1. Install Dependencies

```bash
cd services/dashboard/frontend
npm install
```

### 2. Configure Environment

The `.env` file is already configured to point to the backend at `http://localhost:8000`.

If you need to change it:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

The frontend will be available at **http://localhost:5173**

### 4. Login

Navigate to http://localhost:5173 and login with:
- **Username**: admin
- **Password**: admin123

## Development

### Running the Dev Server

```bash
npm run dev
```

This starts Vite in development mode with:
- Hot module replacement (HMR)
- Fast refresh
- Proxy to backend API at `localhost:8000`

### Building for Production

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

Serves the production build locally for testing.

## API Integration

The frontend communicates with the backend API at `http://localhost:8000`.

### API Client

All API calls go through `src/api/client.ts`, which provides:
- Automatic cookie handling for session auth
- Type-safe methods for all endpoints
- Error handling

### Authentication Flow

1. User enters credentials on login page
2. Frontend calls `POST /api/auth/login`
3. Backend returns session cookie (HTTP-only)
4. Cookie is automatically included in all subsequent requests
5. `AuthContext` manages authentication state

### Data Fetching

React Query is used for all data fetching:
- Automatic caching and refetching
- Loading and error states
- Optimistic updates
- Background refetching

Example:
```typescript
const { data, isLoading } = useQuery({
  queryKey: ['pendingApprovals'],
  queryFn: () => apiClient.getPendingApprovals(),
});
```

## Pages

### Dashboard Home (`/`)
- Summary statistics cards
- Pending approvals alert
- Recent processing runs
- Quick navigation to other sections

### Approval Queue (`/approvals`)
- List of emails requiring review (confidence < 70%)
- Email details with classification info
- Approve/reject/override actions
- Notes field for documentation

### Inbox Monitor (`/inbox`)
- Real-time inbox view
- Filter: unread only / all emails
- Email metadata with classification
- Folder status indicators

### Statistics (`/stats`)
- Classification accuracy metrics
- Category breakdown chart
- Daily trends chart
- Override rate tracking

### Settings (`/settings`)
- Whitelist management
- Add/remove companies
- Company history and notes

## Styling

### TailwindCSS

The project uses TailwindCSS for styling with a custom theme:

```javascript
colors: {
  primary: {
    50: '#eff6ff',
    // ... through ...
    900: '#1e3a8a',
  }
}
```

### Responsive Design

All pages are responsive and mobile-friendly:
- Desktop: Full navigation, multi-column layouts
- Tablet: Adapted layouts
- Mobile: Hamburger menu, single column

## Type Safety

### TypeScript Types

All types are defined in `src/types/index.ts`:
- `User` - User session info
- `Email` - Email data
- `Approval` - Approval request
- `Classification` - AI classification result
- `ProcessRun` - Processing statistics
- And more...

### Type-Safe API Client

The API client methods are fully typed:
```typescript
async getCurrentInbox(refresh = false): Promise<Email[]>
async approveEmail(approvalId: number, ...): Promise<any>
```

## State Management

### Authentication State

Managed by `AuthContext`:
```typescript
const { user, isAuthenticated, login, logout } = useAuth();
```

### Server State

Managed by React Query:
- Automatic caching with `queryKey`
- Background refetching
- Mutation handling with `useMutation`

## Performance

### Optimizations

- Vite's fast HMR for instant feedback
- React Query caching reduces API calls
- Lazy loading with code splitting (future)
- Optimized production builds with tree shaking

### Bundle Size

Production build is optimized with:
- Minification
- Tree shaking
- Chunk splitting
- Gzip compression

## Troubleshooting

### CORS Errors

**Error**: `Access-Control-Allow-Origin` error

**Solution**: Ensure backend is running and CORS is configured:
```python
# backend api/main.py
CORS_ORIGINS=http://localhost:5173
```

### Authentication Fails

**Error**: Login returns 401 Unauthorized

**Solutions**:
1. Verify backend is running at http://localhost:8000
2. Check `ADMIN_PASSWORD_HASH` is set in backend `.env`
3. Try default credentials: admin / admin123

### API Connection Refused

**Error**: `ERR_CONNECTION_REFUSED`

**Solution**: Start the backend API server:
```bash
cd services/dashboard/api
python main.py
```

### Port Already in Use

**Error**: Port 5173 is already in use

**Solution**: Kill the process or change the port in `vite.config.ts`:
```typescript
server: {
  port: 5174, // Change to different port
}
```

## Testing

### Manual Testing Checklist

- [ ] Login with correct credentials
- [ ] Login fails with wrong credentials
- [ ] Dashboard displays statistics
- [ ] Approval queue shows pending emails
- [ ] Can approve/reject emails
- [ ] Inbox monitor shows emails
- [ ] Refresh button fetches latest data
- [ ] Statistics charts render
- [ ] Can add/remove whitelist companies
- [ ] Logout works correctly

### Browser Testing

Tested on:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Future Enhancements

### Phase 2 Features
- Server-Sent Events (SSE) for real-time updates
- Email detail modal with full body
- Bulk actions (approve multiple emails)
- Advanced filtering and search
- Export data to CSV

### Phase 3 Features
- Dark mode
- Mobile app (React Native)
- Email composer (reply to emails)
- Calendar integration
- Push notifications

## Deployment

### Production Build

```bash
npm run build
```

Creates optimized files in `dist/`.

### Hosting Options

**Static Hosting** (Recommended):
- Vercel
- Netlify
- Cloudflare Pages

**Steps**:
1. Build the project: `npm run build`
2. Deploy `dist/` folder
3. Configure environment variable: `VITE_API_BASE_URL=https://your-api.com`
4. Set up redirects for client-side routing

Example `_redirects` file for Netlify:
```
/*    /index.html   200
```

### Environment Variables

Production `.env`:
```
VITE_API_BASE_URL=https://api.yourdomain.com
```

## Contributing

When adding new features:
1. Add TypeScript types to `src/types/index.ts`
2. Add API methods to `src/api/client.ts`
3. Use React Query for data fetching
4. Follow existing component patterns
5. Ensure responsive design
6. Test on multiple browsers

## Support

For issues or questions:
1. Check this README
2. Review the [backend README](../README.md)
3. Check browser console for errors
4. Verify backend API is running

## License

Internal use only - Colaberry Novedea AI Projects
