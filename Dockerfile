FROM ubuntu:22.04

# ইনপুট প্রম্পট বন্ধ রাখা
ENV DEBIAN_FRONTEND=noninteractive

# সিস্টেম প্যাকেজ, পাইথন এবং জাভা ইন্সটল
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk-headless \
    python3 \
    python3-pip \
    wget \
    unzip \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Android SDK ও Build-tools সেটআপ
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH="${PATH}:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/build-tools/34.0.0"

RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmdline-tools.zip && \
    unzip -q /tmp/cmdline-tools.zip -d ${ANDROID_HOME}/cmdline-tools && \
    mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest && \
    rm /tmp/cmdline-tools.zip

# লাইসেন্স এক্সেপ্ট ও Build-tools 34 ডাউনলোড
RUN yes | sdkmanager --licenses && \
    sdkmanager "build-tools;34.0.0" "platforms;android-34"

WORKDIR /app

# APK সাইন করার জন্য ডিফল্ট Keystore তৈরি
RUN keytool -genkey -v -keystore /app/debug.keystore -alias androiddebugkey -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# রেন্ডার পোর্টে সার্ভার চালু করা
CMD ["sh", "-c", "python3 -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
