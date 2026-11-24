// Las versiones se fijan aquí y los módulos no las repiten: dos módulos con
// versiones distintas del mismo complemento es un error que solo aparece al
// compilar y cuyo mensaje no dice cuál de los dos está mal.
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.24" apply false
}
