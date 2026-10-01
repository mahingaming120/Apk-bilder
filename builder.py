import os
import re
import io
import shutil
import subprocess
from PIL import Image

ANDROID_JAR = "/opt/android-sdk/platforms/android-34/android.jar"
KEYSTORE = "/app/debug.keystore"

def clean_package_name(pkg: str) -> str:
    pkg = re.sub(r'[^a-zA-Z0-9_.]', '', pkg.lower().strip())
    parts = [p for p in pkg.split('.') if p]
    if len(parts) < 2:
        return f"com.app.{pkg if pkg else 'myapp'}"
    return ".".join(parts)

def escape_for_android_xml(text: str) -> str:
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace("'", "\\'")
    text = text.replace('"', '\\"')
    text = text.replace('@', '\\@')
    text = text.replace('?', '\\?')
    return text

def run_cmd(cmd, step_name):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise Exception(f"{step_name} এরর: {res.stderr.strip() or res.stdout.strip()}")

def build_apk(work_dir: str, app_name: str, package_name: str, mode: str, target_url: str, html_code: str, logo_bytes: bytes) -> str:
    pkg = clean_package_name(package_name)
    pkg_path = pkg.replace('.', '/')
    
    res_dir = os.path.join(work_dir, "res")
    values_dir = os.path.join(res_dir, "values")
    assets_dir = os.path.join(work_dir, "assets")
    src_dir = os.path.join(work_dir, "src", pkg_path)
    obj_dir = os.path.join(work_dir, "obj")
    
    densities = {
        "mipmap-mdpi": (48, 48),
        "mipmap-hdpi": (72, 72),
        "mipmap-xhdpi": (96, 96),
        "mipmap-xxhdpi": (144, 144),
        "mipmap-xxxhdpi": (192, 192)
    }
    
    for d in densities.keys():
        os.makedirs(os.path.join(res_dir, d), exist_ok=True)
    os.makedirs(values_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(obj_dir, exist_ok=True)

    # ১. লোগো রিসাইজ
    img = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
    for folder, size in densities.items():
        resized = img.resize(size, Image.Resampling.LANCZOS)
        resized.save(os.path.join(res_dir, folder, "ic_launcher.png"), "PNG")

    # ২. XML নিরাপদ Strings.xml
    safe_xml_app_name = escape_for_android_xml(app_name)
    with open(os.path.join(values_dir, "strings.xml"), "w", encoding="utf-8") as f:
        f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{safe_xml_app_name}</string>
</resources>''')

    # ৩. Fullscreen AndroidManifest.xml (Android 14/15 কমপ্যাটিবিলিটি সহ)
    manifest_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{pkg}"
    android:versionCode="1"
    android:versionName="1.0">

    <uses-sdk
        android:minSdkVersion="24"
        android:targetSdkVersion="34" />

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher"
        android:usesCleartextTraffic="true"
        android:theme="@android:style/Theme.NoTitleBar.Fullscreen">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>'''

    manifest_path = os.path.join(work_dir, "AndroidManifest.xml")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest_xml)

    # ৪. URL নাকি HTML লোড করবে
    if mode == "html":
        with open(os.path.join(assets_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_code or "<h1>App Ready!</h1>")
        load_code = 'myWebView.loadUrl("file:///android_asset/index.html");'
    else:
        url = target_url.strip() if target_url else "https://google.com"
        safe_url_java = url.replace('\\', '\\\\').replace('"', '\\"')
        load_code = f'myWebView.loadUrl("{safe_url_java}");'

    # ৫. Fullscreen WebView সম্বলিত MainActivity.java তৈরি
    main_activity_java = f'''package {pkg};

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.view.KeyEvent;
import android.view.Window;
import android.view.WindowManager;

public class MainActivity extends Activity {{
    private WebView myWebView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                             WindowManager.LayoutParams.FLAG_FULLSCREEN);

        myWebView = new WebView(this);
        setContentView(myWebView);

        WebSettings settings = myWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);

        myWebView.setWebViewClient(new WebViewClient());

        {load_code}
    }}

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {{
        if ((keyCode == KeyEvent.KEYCODE_BACK) && myWebView.canGoBack()) {{
            myWebView.goBack();
            return true;
        }}
        return super.onKeyDown(keyCode, event);
    }}
}}'''
    with open(os.path.join(src_dir, "MainActivity.java"), "w", encoding="utf-8") as f:
        f.write(main_activity_java)

    # ৬. বিল্ড পাইপলাইন
    compiled_res = os.path.join(work_dir, "compiled_res.zip")
    unaligned_apk = os.path.join(work_dir, "unaligned.apk")
    aligned_apk = os.path.join(work_dir, "aligned.apk")
    final_apk = os.path.join(work_dir, "output.apk")

    # (a) রিসোর্স কম্পাইল
    run_cmd(["aapt2", "compile", "--dir", res_dir, "-o", compiled_res], "Resource Compile")

    # (b) রিসোর্স লিঙ্ক (SDK Version 24 ও 34 নিশ্চিত করা)
    aapt_link_cmd = [
        "aapt2", "link",
        "-I", ANDROID_JAR,
        "--min-sdk-version", "24",
        "--target-sdk-version", "34",
        "--manifest", manifest_path,
        "-o", unaligned_apk,
        "--auto-add-overlay",
        compiled_res,
        "--java", os.path.join(work_dir, "src")
    ]
    if os.path.exists(assets_dir) and os.listdir(assets_dir):
        aapt_link_cmd.extend(["-A", assets_dir])

    run_cmd(aapt_link_cmd, "Resource Link")

    # (c) জাভা কম্পাইল
    java_files = [os.path.join(r, f) for r, d, fs in os.walk(os.path.join(work_dir, "src")) for f in fs if f.endswith(".java")]
    run_cmd(["javac", "-source", "8", "-target", "8", "-cp", ANDROID_JAR, "-d", obj_dir] + java_files, "Java Compile")

    # (d) DEX তৈরি
    class_files = [os.path.join(r, f) for r, d, fs in os.walk(obj_dir) for f in fs if f.endswith(".class")]
    run_cmd(["d8", "--output", work_dir, "--lib", ANDROID_JAR] + class_files, "DEX Generation")

    # (e) APK-তে DEX ফাইল ইনজেক্ট
    run_cmd(["zip", "-j", "-u", unaligned_apk, os.path.join(work_dir, "classes.dex")], "ZIP Dex")

    # (f) Zipalign
    run_cmd(["zipalign", "-f", "-p", "4", unaligned_apk, aligned_apk], "Zipalign")

    # (g) ডিজিটাল সাইন
    run_cmd([
        "apksigner", "sign",
        "--ks", KEYSTORE,
        "--ks-pass", "pass:android",
        "--key-pass", "pass:android",
        "--out", final_apk,
        aligned_apk
    ], "APK Sign")

    return final_apk
