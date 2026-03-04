import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.fieldops.app',
  appName: 'Field Ops',
  // Point to your live production URL instead of a local build
  server: {
    url: 'https://your-production-domain.com',  // TODO: Replace with your actual domain
    cleartext: false,                             // HTTPS only
  },
  // Web directory (placeholder — not used when server.url is set)
  webDir: 'www',
  plugins: {
    StatusBar: {
      style: 'Dark',       // Light text on dark background
      backgroundColor: '#0a0a0a',
    },
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: '#0a0a0a',
      showSpinner: false,
      launchAutoHide: true,
    },
    Keyboard: {
      resize: 'body',      // Resize webview when keyboard opens
      resizeOnFullScreen: true,
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
  ios: {
    contentInset: 'automatic',
    backgroundColor: '#0a0a0a',
    preferredContentMode: 'mobile',
    allowsLinkPreview: false,
  },
  android: {
    backgroundColor: '#0a0a0a',
    allowMixedContent: false,
  },
};

export default config;
