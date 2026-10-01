@rem Pydrud Gradle launcher for Windows.
@rem
@rem Uses gradle-wrapper.jar when present; otherwise downloads the Gradle
@rem distribution declared in gradle-wrapper.properties once into
@rem %USERPROFILE%\.gradle\pydrud-dists and reuses it.
@if "%DEBUG%"=="" @echo off
setlocal enabledelayedexpansion

set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.
set APP_HOME=%DIRNAME%
set DEFAULT_JVM_OPTS=-Xmx2048m -Xms256m
set WRAPPER_JAR=%APP_HOME%gradle\wrapper\gradle-wrapper.jar
set WRAPPER_PROPS=%APP_HOME%gradle\wrapper\gradle-wrapper.properties

if defined JAVA_HOME (
    set JAVA_EXE=%JAVA_HOME%\bin\java.exe
) else (
    set JAVA_EXE=java.exe
)
"%JAVA_EXE%" -version >NUL 2>&1
if errorlevel 1 (
    echo ERROR: Java not found. Install JDK 17+ and set JAVA_HOME. See: pydrud doctor
    exit /b 1
)

if exist "%WRAPPER_JAR%" (
    "%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% -classpath "%WRAPPER_JAR%" org.gradle.wrapper.GradleWrapperMain %*
    exit /b %ERRORLEVEL%
)

set DIST_URL=https://services.gradle.org/distributions/gradle-8.14.4-bin.zip
if exist "%WRAPPER_PROPS%" (
    for /f "tokens=1,* delims==" %%a in ('findstr /b "distributionUrl" "%WRAPPER_PROPS%"') do set RAW_URL=%%b
    if defined RAW_URL set DIST_URL=!RAW_URL:\:=:!
)

for %%F in ("!DIST_URL!") do set DIST_NAME=%%~nF
set GRADLE_VER=!DIST_NAME:gradle-=!
set GRADLE_VER=!GRADLE_VER:-bin=!
set GRADLE_VER=!GRADLE_VER:-all=!
set DIST_HOME=%USERPROFILE%\.gradle\pydrud-dists
set GRADLE_BIN=!DIST_HOME!\gradle-!GRADLE_VER!\bin\gradle.bat

if not exist "!GRADLE_BIN!" (
    where gradle >NUL 2>&1
    if not errorlevel 1 (
        echo [Pydrud] Using system Gradle
        gradle %*
        exit /b !ERRORLEVEL!
    )
    echo [Pydrud] Downloading Gradle !GRADLE_VER! once...
    if not exist "!DIST_HOME!" mkdir "!DIST_HOME!"
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '!DIST_URL!' -OutFile '!DIST_HOME!\dist.zip'" || exit /b 1
    powershell -NoProfile -Command "Expand-Archive -Force '!DIST_HOME!\dist.zip' '!DIST_HOME!'" || exit /b 1
    del "!DIST_HOME!\dist.zip"
)

"!GRADLE_BIN!" %*
exit /b %ERRORLEVEL%
