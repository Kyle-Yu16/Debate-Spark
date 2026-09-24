# 观点火花 Android

原生 Android 客户端，最低支持 Android 8.0（API 26）。它直接调用用户配置的 OpenAI-compatible Chat Completions 接口，不需要部署 Web 后端。

## 隐私与数据

- API Key 通过 Android Keystore 的 AES-GCM 密钥加密后保存在应用私有偏好设置中。
- Base URL、模型名、辩题、备赛简报和对辩记录全部保存在设备本地。
- 仅当用户主动点击「生成备赛简报」「发送发言」或「测试连接」时，相关请求内容会发送给用户自行配置的模型服务。
- 卸载应用将删除本地项目与配置；正式上架前建议将 release 签名替换为私有上传密钥。

## 使用

1. 安装仓库根目录 `releases/` 中的 APK。
2. 进入「模型连接」，填写 API Key、Base URL 和 Model。
3. 新建辩题；可生成备赛简报，或直接在「人机对辩」进行自由辩论。

Base URL 可以填写 `https://api.example.com/v1`，应用会自动补全 `/chat/completions`；也可直接填写完整接口路径。

## 构建

```bash
cd android
./gradlew :app:assembleRelease
```

输出路径：`app/build/outputs/apk/release/app-release.apk`。
