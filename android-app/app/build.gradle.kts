plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "uk.familycontrol.remote"
    compileSdk = 35

    defaultConfig {
        applicationId = "uk.familycontrol.remote"
        minSdk = 26
        targetSdk = 35
        versionCode = 7
        versionName = "0.4.2-updates-preview"
    }
    // The applicationId is unchanged so Android recognises this as the same app.
    // In-place installation ALSO requires the previous APK signing certificate.
    // Production signing uses private CI secrets; never commit keystores to GitHub.
    signingConfigs {
        create("parentpilotRelease") {
            val keyPath = System.getenv("PARENTPILOT_SIGNING_STORE")
            if (!keyPath.isNullOrBlank()) {
                storeFile = file(keyPath)
                storePassword = System.getenv("PARENTPILOT_SIGNING_STORE_PASSWORD")
                keyAlias = System.getenv("PARENTPILOT_SIGNING_KEY_ALIAS")
                keyPassword = System.getenv("PARENTPILOT_SIGNING_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
            if (!System.getenv("PARENTPILOT_SIGNING_STORE").isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("parentpilotRelease")
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

// Scoped APK-sharing provider. No public storage access is required.
dependencies {
    implementation("androidx.core:core:1.15.0")
}
