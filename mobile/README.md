# Mobile App (Scaffold)

This folder contains guidance for a cross-platform mobile app. Recommended approach: React Native + Expo for rapid prototyping.

Suggested structure

- `mobile/app/` — React Native project (Expo)
- `mobile/native-modules/` — BLE helper modules (react-native-ble-plx) and camera integrations

Quickstart (create project):

```bash
npx create-expo-app mobile/app
cd mobile/app
expo install react-native-ble-plx expo-camera
```

Important features to implement in mobile app:
- Camera module with guided framing overlay and white-balance calibration reference
- BLE pairing and ingestion of device telemetry
- Offline caching and upload retry
- Auth and secure storage of tokens
