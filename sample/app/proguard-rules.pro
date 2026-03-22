# ================================
# Tinker ProGuard Rules
# ================================

# Tinker 核心类（插件会自动添加大部分规则，以下为补充）
-keepattributes *Annotation*
-dontwarn com.tencent.tinker.loader.**
-keep public class * extends com.tencent.tinker.loader.app.TinkerApplication
-keep public class * extends com.tencent.tinker.loader.app.DefaultApplicationLike

# Tinker 注解
-keep @com.tencent.tinker.anno.DefaultLifeCycle public class *

# 自定义 ResultService
-keep public class * extends com.tencent.tinker.lib.service.DefaultTinkerResultService

# ================================
# 通用 Android 规则
# ================================
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keepattributes SourceFile,LineNumberTable
