# FieldLgx — iOS & Android App Publishing Guide

This guide walks you through building and publishing the FieldLgx native app wrapper using Capacitor. The native app is a thin WebView shell that loads your live Django site — no separate frontend build step needed.

---

## Prerequisites

**For both platforms:**
- Node.js 18+ and npm
- Your production domain live and accessible over HTTPS

**For iOS:**
- macOS with Xcode 15+ installed
- Apple Developer account ($99/year) — https://developer.apple.com/programs/
- A physical iPhone/iPad for testing (simulator works for dev, but you need a device for TestFlight)

**For Android:**
- Android Studio (any OS) — https://developer.android.com/studio
- Google Play Developer account ($25 one-time) — https://play.google.com/console
- A physical Android device or emulator for testing

---

## Step 1: Initial Setup

```bash
cd native/

# Install dependencies
npm install

# Create the www placeholder (already done)
# Initialize Capacitor platforms
npx cap add ios
npx cap add android
npx cap sync
```

---

## Step 2: Configure Your Production URL

Edit `capacitor.config.ts` and replace the placeholder URL:

```ts
server: {
  url: 'https://your-actual-domain.com',  // Your live FieldLgx URL
  cleartext: false,
},
```

Then sync the config:
```bash
npx cap sync
```

---

## Step 3: App Icons & Splash Screen

You need app icons in multiple sizes. Use your existing logo files:

### iOS Icons (required sizes)
Place in `ios/App/App/Assets.xcassets/AppIcon.appiconset/`:
- 1024x1024 (App Store)
- 180x180 (iPhone @3x)
- 120x120 (iPhone @2x)
- 167x167 (iPad Pro @2x)
- 152x152 (iPad @2x)
- 76x76 (iPad @1x)

**Easiest method:** Use https://www.appicon.co — upload your 1024x1024 icon and it generates all sizes.

### Android Icons
Place in `android/app/src/main/res/`:
- `mipmap-xxxhdpi/ic_launcher.png` (192x192)
- `mipmap-xxhdpi/ic_launcher.png` (144x144)
- `mipmap-xhdpi/ic_launcher.png` (96x96)
- `mipmap-hdpi/ic_launcher.png` (72x72)
- `mipmap-mdpi/ic_launcher.png` (48x48)

**Easiest method:** In Android Studio, right-click `res` → New → Image Asset → choose your icon.

### Splash Screen
The splash screen uses the `SplashScreen` plugin config. For a custom image:
1. Create a centered logo image on `#0a0a0a` background
2. iOS: Place in `ios/App/App/Assets.xcassets/Splash.imageset/`
3. Android: Place in `android/app/src/main/res/drawable/splash.png`

---

## Step 4: Build & Test Locally

### iOS
```bash
npx cap open ios
```
This opens Xcode. Then:
1. Select your signing team (your Apple Developer account)
2. Select a simulator or connected device
3. Press **Cmd+R** to build and run
4. The app should load your production site in the native shell

### Android
```bash
npx cap open android
```
This opens Android Studio. Then:
1. Wait for Gradle sync to complete
2. Select an emulator or connected device
3. Press the green **Run** button
4. The app should load your production site

---

## Step 5: Publish to App Store (iOS)

### 5a. App Store Connect Setup
1. Go to https://appstoreconnect.apple.com
2. Click **My Apps** → **+** → **New App**
3. Fill in:
   - **Name:** FieldLgx
   - **Bundle ID:** com.fieldlgx.app
   - **SKU:** fieldlgx-001
   - **Primary Language:** English

### 5b. Prepare Store Listing
You need:
- **Screenshots:** At least 3 per device size (iPhone 6.7", iPhone 6.5", iPad 12.9")
  - Take screenshots in Xcode Simulator: Window → Screenshot
  - Show: Dashboard, Job list, Invoice, Calendar
- **App Icon:** 1024x1024 PNG (no transparency, no rounded corners)
- **Description:** ~150 words about what FieldLgx does
- **Keywords:** lawn care, landscaping, field service, invoicing, scheduling
- **Support URL:** Your website
- **Privacy Policy URL:** Required — create a simple one at your domain

### 5c. Build & Upload
In Xcode:
1. Select **Any iOS Device** as the build target
2. **Product** → **Archive**
3. In the Organizer window, click **Distribute App**
4. Choose **App Store Connect** → **Upload**
5. Wait for processing (5-15 minutes)

### 5d. Submit for Review
In App Store Connect:
1. Select your build under the new version
2. Fill in "What's New" notes
3. Set pricing (Free is fine — your SaaS billing is handled in-app)
4. Click **Submit for Review**
5. Review typically takes 24-48 hours

### Common rejection reasons to avoid:
- Missing privacy policy URL
- App doesn't work without internet (add an offline error screen)
- Screenshots don't match app functionality
- Login-required apps need a demo account for reviewers

---

## Step 6: Publish to Google Play (Android)

### 6a. Generate Signed APK/AAB
In Android Studio:
1. **Build** → **Generate Signed Bundle / APK**
2. Choose **Android App Bundle** (AAB) — required by Google Play
3. Create a new keystore:
   - **Key store path:** `native/fieldlgx-release.keystore`
   - **Password:** Choose a strong password (save this!)
   - **Key alias:** fieldlgx
   - **Validity:** 25 years
4. Select **release** build variant
5. Click **Finish** — output is at `android/app/release/app-release.aab`

**IMPORTANT:** Back up your keystore file and password. You cannot update the app without them.

### 6b. Google Play Console Setup
1. Go to https://play.google.com/console
2. **Create app** → Fill in:
   - **App name:** FieldLgx
   - **Default language:** English
   - **App type:** App
   - **Free or paid:** Free

### 6c. Store Listing
You need:
- **Short description:** (80 chars) "Field service management for lawn care professionals"
- **Full description:** 150-300 words
- **Screenshots:** At least 2 phone screenshots (min 320px, max 3840px)
- **Feature graphic:** 1024x500 PNG
- **App icon:** 512x512 PNG
- **Privacy policy URL:** Required

### 6d. Upload & Release
1. Go to **Production** → **Create new release**
2. Upload your `.aab` file
3. Add release notes
4. **Review release** → **Start rollout**
5. Review typically takes 1-3 days (can be longer for first submission)

---

## Step 7: App Updates

When you update your Django app, the native app automatically loads the new version — no app store update needed! You only need to push an app update if you change:
- Capacitor plugins
- Native configuration (icons, splash screen, permissions)
- The production URL

---

## Optional Enhancements

### Push Notifications
The `@capacitor/push-notifications` plugin is already included. To enable:
1. Set up Firebase Cloud Messaging (Android) and APNs (iOS)
2. Add a Django endpoint to register device tokens
3. Send push notifications from your Django backend using `firebase-admin` or `apns2`

### Deep Links
To handle URLs like `fieldlgx://jobs/123`:
1. Add URL scheme in Xcode (iOS) and AndroidManifest.xml
2. Configure Capacitor's App plugin to handle deep links

### Offline Support
Add a service worker to cache critical assets:
1. Register a service worker in your Django template
2. Cache the CSS, JS, and key pages
3. Show a friendly "No connection" screen when offline

---

## Costs Summary

| Item | Cost |
|------|------|
| Apple Developer Account | $99/year |
| Google Play Developer Account | $25 one-time |
| Capacitor (open source) | Free |
| Total first year | ~$124 |
| Total subsequent years | $99/year |

---

## Troubleshooting

**App shows blank white screen:**
- Check that your production URL is correct in `capacitor.config.ts`
- Ensure HTTPS is working on your domain
- Check Xcode/Android Studio console for network errors

**iOS: "App Transport Security" error:**
- Your server MUST use HTTPS. HTTP is blocked by default on iOS.

**Android: Mixed content blocked:**
- Ensure all resources (images, CSS, JS) are loaded over HTTPS
- `allowMixedContent` is set to `false` for security

**Keyboard covers input fields:**
- The Keyboard plugin's `resize: 'body'` should handle this
- If not, add `padding-bottom` when keyboard is visible using Capacitor's Keyboard events

**Safe area issues (notch/home indicator):**
- Already handled in base.html with `env(safe-area-inset-*)` values
- Add `<meta name="viewport" content="viewport-fit=cover">` if not present
