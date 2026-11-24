plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "mx.com.nexum.bienestar"
    compileSdk = 34

    defaultConfig {
        applicationId = "mx.com.nexum.bienestar"
        minSdk = 26          // EncryptedSharedPreferences necesita API 23+;
                             // 26 además garantiza el almacén de claves con
                             // respaldo de hardware en la mayoría de equipos.
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        // Las direcciones de los servicios NO se escriben en el código: cada
        // variante de compilación trae la suya. Con una constante en el
        // código, cambiar de ambiente obligaría a recompilar a mano y
        // alguien acabaría publicando una versión apuntando a developer.
        buildConfigField("String", "URL_AUTH", "\"http://10.0.2.2:8101\"")
        buildConfigField("String", "URL_CATALOGOS", "\"http://10.0.2.2:8103\"")
        buildConfigField("String", "URL_PROCESO", "\"http://10.0.2.2:8104\"")
        buildConfigField("String", "URL_DOCUMENTOS", "\"http://10.0.2.2:8105\"")
        buildConfigField("String", "URL_NOTIFICACIONES", "\"http://10.0.2.2:8106\"")
    }

    buildTypes {
        debug {
            // 10.0.2.2 es como el emulador de Android ve el 127.0.0.1 de la
            // máquina anfitriona. En un teléfono físico hay que poner la IP
            // de la computadora en la red local.
            isDebuggable = true
        }
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // En release las direcciones son HTTPS y el manifiesto prohíbe
            // el tráfico en claro: ver network_security_config.xml.
            buildConfigField("String", "URL_AUTH", "\"https://auth.bienestar.nexum.com.mx\"")
            buildConfigField("String", "URL_CATALOGOS", "\"https://catalogos.bienestar.nexum.com.mx\"")
            buildConfigField("String", "URL_PROCESO", "\"https://proceso.bienestar.nexum.com.mx\"")
            buildConfigField("String", "URL_DOCUMENTOS", "\"https://documentos.bienestar.nexum.com.mx\"")
            buildConfigField("String", "URL_NOTIFICACIONES", "\"https://avisos.bienestar.nexum.com.mx\"")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")

    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // Almacenamiento cifrado del token y del borrador. Es una de las dos
    // capacidades del dispositivo que usa esta aplicación.
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // La cámara se usa por intención del sistema (TakePicture), que no
    // necesita CameraX: menos dependencias y menos permisos.
    implementation("androidx.exifinterface:exifinterface:1.3.7")

    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation(platform("androidx.compose:compose-bom:2024.06.00"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
