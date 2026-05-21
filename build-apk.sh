#!/bin/bash
# Build offline APK for study-app (no server needed)
# Usage: ./build-apk.sh

set -e

cd "$(dirname "$0")"

echo "🔧 构建离线 APK（无服务器依赖）"

# Ensure capacitor config is correct
cat > capacitor.config.json << EOF
{
  "appId": "com.study.addict",
  "appName": "上瘾学习",
  "webDir": "static",
  "server": {
    "androidScheme": "https"
  }
}
EOF

# Sync
echo "📱 同步 Android 平台..."
npx cap sync android 2>&1 | tail -5

# Build
echo "🔨 构建 APK..."
cd android
./gradlew assembleRelease 2>&1 | tail -10

# Sign
APK="app/build/outputs/apk/release/app-release-unsigned.apk"
if [ -f "$APK" ]; then
  echo "✏️ 签名..."
  if [ ! -f ~/.android/debug.keystore ]; then
    mkdir -p ~/.android
    keytool -genkey -v -keystore ~/.android/debug.keystore -storepass android \
      -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
      -dname "CN=Android Debug,O=Android,C=US"
  fi
  export ANDROID_HOME=${ANDROID_HOME:-/opt/android-sdk}
  $ANDROID_HOME/build-tools/34.0.0/apksigner sign --ks ~/.android/debug.keystore \
    --ks-pass pass:android --ks-key-alias androiddebugkey "$APK"
  # Copy
  cp "$APK" "../static/上瘾学习-offline-v1.apk"
  echo "✅ 离线APK构建成功!"
  ls -lh "../static/上瘾学习-offline-v1.apk"
else
  echo "❌ APK 构建失败"
  exit 1
fi
