# Traffic Enhancer — mobile development foundation

This is an **initial Expo SDK 58 / React Native 0.88 app source project** targeting Android and iOS, **not a tested release binary**. It supports user-initiated Files/document-picker import, foreground upload to the current development API, incident-list polling while processing, and preliminary PDF export through the OS share sheet.

There is **no** camera connection, no fully automatic DDPAI import, no background or resumable upload queue, no native share-receiver integration, and no real-device acceptance test yet. The shared development operator key must be replaced by actual user authentication before launch.

## Start

Requires Node.js 22.13+ and the appropriate Expo / Android Studio / Xcode toolchain.

~~~bash
cd apps/mobile
npm install
npm run typecheck
npm start
~~~

Install compatible packages using Expo's installer if upgrading: \`npx expo install --fix\`.

Run FastAPI separately from the repo root. In the mobile UI, enter a backend address that the **actual device can reach** and the operator key configured in \`TE_API_KEY\`. \`localhost\` on a physical phone refers to the phone itself, **not** your laptop. Use a controlled development-only HTTPS endpoint for physical devices.

The upload uses \`expo-document-picker\` with \`copyToCacheDirectory: true\` and the documented \`expo/fetch\` multipart request with \`expo-file-system\` File, not an invented dashcam API. A video first needs to be accessible through the system Files picker. The report is rendered on the backend and shared as PDF with \`expo-sharing\`.

SDK documentation:
- https://docs.expo.dev/versions/latest/sdk/document-picker/
- https://docs.expo.dev/versions/latest/sdk/filesystem/
- https://docs.expo.dev/versions/latest/sdk/sharing/

A production-ready version must add protected multi-user auth, persistent local evidence queue, connectivity-aware retries, background upload where officially supported, security tests, native share extensions, and physical Android/iPhone tests.
