plugins {
    id("com.android.application")
    // START: FlutterFire Configuration
    id("com.google.gms.google-services")
    // END: FlutterFire Configuration
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.builtwithporpoise.jokes"
    compileSdk = 36
    ndkVersion = "29.0.13113456"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_1_8.toString()
    }

    defaultConfig {
        applicationId = "com.builtwithporpoise.jokes"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 23
        targetSdk = 36
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        multiDexEnabled = true
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    // Import the Firebase BoM
    implementation(platform("com.google.firebase:firebase-bom:33.9.0"))

    // Firebase analytics
    implementation("com.google.firebase:firebase-analytics")

    // Add the dependencies for any other desired Firebase products
    implementation("com.google.android.play:integrity:1.4.0")

    // Add Google Play Services auth
    implementation("com.google.android.gms:play-services-auth:20.7.0")

    // Add Google Play Services base
    implementation("com.google.android.gms:play-services-base:18.+")

    // Core library desugaring
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.3")
}