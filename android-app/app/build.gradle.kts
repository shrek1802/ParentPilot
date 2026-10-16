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
        versionCode = 1
        versionName = "0.3-preview"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
